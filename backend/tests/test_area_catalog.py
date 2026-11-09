"""F2-2 — garante que o catálogo documentado em constants.py nunca diverge
do catálogo real da tabela autoitil.area_responsavel. Integração real
contra o Postgres do docker-compose.yml."""

from sqlalchemy import select

from app.domain.constants import AREA_RESPONSAVEL_CATALOG
from app.domain.db import SessionLocal
from app.domain.models import AreaResponsavel


def test_area_catalog_matches_database():
    with SessionLocal() as session:
        db_areas = set(session.scalars(select(AreaResponsavel.nome)))

    assert set(AREA_RESPONSAVEL_CATALOG) == db_areas
