"""Testes de app.auth.security: hash/verificação de senha (bcrypt) e
emissão/decodificação de JWT — funções puras, sem banco."""

from datetime import UTC, datetime, timedelta

import jwt

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.domain.models import Usuario


def _fake_usuario(**overrides) -> Usuario:
    defaults = {"id": 1, "email": "teste@autoitil.test", "is_admin": False}
    defaults.update(overrides)
    return Usuario(**defaults)


class TestHashPassword:
    def test_verify_password_accepts_correct_password(self):
        hash_ = hash_password("senha-correta")
        assert verify_password("senha-correta", hash_) is True

    def test_verify_password_rejects_wrong_password(self):
        hash_ = hash_password("senha-correta")
        assert verify_password("senha-errada", hash_) is False

    def test_hash_is_not_the_plain_password(self):
        hash_ = hash_password("senha-correta")
        assert hash_ != "senha-correta"


class TestAccessToken:
    def test_decode_returns_the_same_fields_encoded(self):
        usuario = _fake_usuario(id=42, email="ana@autoitil.test", is_admin=True)
        token = create_access_token(usuario)

        payload = decode_access_token(token)

        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["email"] == "ana@autoitil.test"
        assert payload["is_admin"] is True

    def test_decode_returns_none_for_invalid_signature(self):
        usuario = _fake_usuario()
        token = create_access_token(usuario)
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

        assert decode_access_token(tampered) is None

    def test_decode_returns_none_for_expired_token(self):
        usuario = _fake_usuario()
        expired_payload = {
            "sub": str(usuario.id),
            "email": usuario.email,
            "is_admin": usuario.is_admin,
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            expired_payload, settings.JWT_SECRET_KEY, algorithm="HS256"
        )

        assert decode_access_token(expired_token) is None

    def test_decode_returns_none_for_garbage_token(self):
        assert decode_access_token("isso-nao-e-um-jwt") is None
