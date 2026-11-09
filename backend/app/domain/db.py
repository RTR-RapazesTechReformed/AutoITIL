"""Engine e session factory do SQLAlchemy para o Postgres do projeto.

Sem Alembic — o schema é aplicado via db/autoitil_schema_v4.sql (script SQL
completo, versionado manualmente). Este módulo só configura a conexão.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://autoitil:autoitil@localhost:5432/autoitil",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    # client_encoding fixo: get_or_create_default_organizacao compara
    # organizacao.nome por igualdade de string ("Organização Padrão", com
    # acentuação) — uma conexão com encoding diferente do usado ao semear
    # esse nome (migração 008) produziria bytes diferentes pro "mesmo"
    # nome e criaria uma segunda organização "default" silenciosamente
    # (ver issue #25).
    connect_args={"client_encoding": "utf8"},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
