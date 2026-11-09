"""custos_routes.py — fechamento e consulta de relatório de custo por
organização. Dashboard interna de gasto, não cobrança de cliente. Ver
app.custos.relatorios e

Ordem de registro importa: /api/custos/preview precisa vir ANTES de
/api/custos/{relatorio_id} — senão o FastAPI tentaria casar "preview" como
valor de relatorio_id (int) e devolveria 422 em vez de rodar o preview."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, model_validator

from app.custos.relatorios import (
    PeriodoJaFechadoError,
    detalhar_relatorio_custo,
    fechar_periodo,
    listar_relatorios_custo,
    preview_periodo_aberto,
)
from app.domain.db import SessionLocal

router = APIRouter()


class FecharPeriodoRequest(BaseModel):
    periodo_inicio: date
    periodo_fim: date

    @model_validator(mode="after")
    def _periodo_fim_apos_periodo_inicio(self) -> FecharPeriodoRequest:
        if self.periodo_fim <= self.periodo_inicio:
            raise ValueError("periodo_fim deve ser posterior a periodo_inicio.")
        return self


def _require_admin(request: Request) -> JSONResponse | None:
    if not request.state.usuario.get("is_admin"):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": {"code": "FORBIDDEN", "message": "Requer privilégio de administrador."},
            },
        )
    return None


@router.post("/api/admin/custos/fechar")
def fechar_periodo_route(payload: FecharPeriodoRequest, request: Request) -> JSONResponse:
    forbidden = _require_admin(request)
    if forbidden:
        return forbidden
    organizacao_id = request.state.usuario["organizacao_id"]
    with SessionLocal() as session:
        try:
            relatorio = fechar_periodo(
                session,
                organizacao_id=organizacao_id,
                periodo_inicio=payload.periodo_inicio,
                periodo_fim=payload.periodo_fim,
            )
            session.commit()
        except PeriodoJaFechadoError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "error": {"code": "PERIODO_JA_FECHADO", "message": str(exc)},
                },
            )
        return JSONResponse(status_code=201, content={"success": True, "data": relatorio})


@router.get("/api/custos/preview")
def preview_custo_route(request: Request) -> JSONResponse:
    organizacao_id = request.state.usuario["organizacao_id"]
    with SessionLocal() as session:
        preview = preview_periodo_aberto(session, organizacao_id=organizacao_id)
        return JSONResponse(content={"success": True, "data": preview})


@router.get("/api/custos")
def listar_custos_route(request: Request) -> JSONResponse:
    organizacao_id = request.state.usuario["organizacao_id"]
    with SessionLocal() as session:
        relatorios = listar_relatorios_custo(session, organizacao_id=organizacao_id)
        return JSONResponse(content={"success": True, "data": relatorios})


@router.get("/api/custos/{relatorio_id}")
def detalhar_custo_route(relatorio_id: int, request: Request) -> JSONResponse:
    organizacao_id = request.state.usuario["organizacao_id"]
    with SessionLocal() as session:
        relatorio = detalhar_relatorio_custo(
            session, organizacao_id=organizacao_id, relatorio_custo_id=relatorio_id
        )
        if relatorio is None:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": {"code": "RELATORIO_NOT_FOUND", "message": "Relatório de custo não encontrado."},
                },
            )
        return JSONResponse(content={"success": True, "data": relatorio})
