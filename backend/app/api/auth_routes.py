"""auth_routes.py — login, /me e administração de usuários. Ver
app.api.auth (o middleware que popula request.state.usuario)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.auth.security import create_access_token
from app.auth.service import (
    authenticate,
    create_user,
    list_users,
    set_user_admin,
    set_user_ativo,
)
from app.domain.db import SessionLocal
from app.domain.models import Usuario

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1)
    senha: str = Field(..., min_length=1)


class CreateUserRequest(BaseModel):
    email: str = Field(..., min_length=1)
    senha: str = Field(..., min_length=1)
    is_admin: bool = False


class PatchUserRequest(BaseModel):
    ativo: bool | None = None
    is_admin: bool | None = None


def _usuario_publico(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "email": usuario.email,
        "is_admin": usuario.is_admin,
    }


def _usuario_admin_publico(usuario: Usuario) -> dict:
    return {**_usuario_publico(usuario), "ativo": usuario.ativo}


def _require_admin(request: Request) -> JSONResponse | None:
    if not request.state.usuario.get("is_admin"):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Requer privilégio de administrador.",
                },
            },
        )
    return None


@router.post("/api/auth/login")
def login(payload: LoginRequest) -> JSONResponse:
    with SessionLocal() as session:
        usuario = authenticate(session, payload.email, payload.senha)
        if usuario is None:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": "Email ou senha inválidos.",
                    },
                },
            )
        token = create_access_token(usuario)
        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "access_token": token,
                    "usuario": _usuario_publico(usuario),
                },
            }
        )


@router.get("/api/auth/me")
def me(request: Request) -> JSONResponse:
    payload = request.state.usuario
    return JSONResponse(
        content={
            "id": int(payload["sub"]),
            "email": payload["email"],
            "is_admin": payload["is_admin"],
            "organizacao_id": payload["organizacao_id"],
        }
    )


@router.post("/api/admin/usuarios")
def criar_usuario(payload: CreateUserRequest, request: Request) -> JSONResponse:
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    with SessionLocal() as session:
        try:
            usuario = create_user(
                session,
                payload.email,
                payload.senha,
                payload.is_admin,
                organizacao_id=request.state.usuario["organizacao_id"],
            )
            session.commit()
        except IntegrityError:
            session.rollback()
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "error": {
                        "code": "EMAIL_ALREADY_EXISTS",
                        "message": "Já existe um usuário com esse email.",
                    },
                },
            )
        return JSONResponse(
            status_code=201,
            content={"success": True, "data": _usuario_admin_publico(usuario)},
        )


@router.get("/api/admin/usuarios")
def listar_usuarios(request: Request) -> JSONResponse:
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    with SessionLocal() as session:
        usuarios = list_users(session, organizacao_id=request.state.usuario["organizacao_id"])
        return JSONResponse(content=[_usuario_admin_publico(u) for u in usuarios])


@router.patch("/api/admin/usuarios/{user_id}")
def atualizar_usuario(
    user_id: int, payload: PatchUserRequest, request: Request
) -> JSONResponse:
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    with SessionLocal() as session:
        usuario = session.get(Usuario, user_id)
        if usuario is None or usuario.organizacao_id != request.state.usuario["organizacao_id"]:
            # Mesma organização do usuário de outra, mesma resposta de "não
            # existe" — não vaza que o id pertence a outra organização (ver
            # issue #17; mesmo padrão de detalhar_relatorio_custo).
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": "Usuário não encontrado.",
                    },
                },
            )
        if payload.ativo is not None:
            usuario = set_user_ativo(session, user_id, payload.ativo)
        if payload.is_admin is not None:
            usuario = set_user_admin(session, user_id, payload.is_admin)
        if payload.ativo is None and payload.is_admin is None:
            session.expunge(usuario)
        session.commit()
        return JSONResponse(
            content={"success": True, "data": _usuario_admin_publico(usuario)}
        )
