"""Testes de app.domain.system_metrics — integração real contra o Postgres
do docker-compose.yml (mesmo padrão de test_upload_history.py). Sem mock de
banco; psutil é chamado de verdade (mede o processo de teste mesmo)."""

from app.domain.db import SessionLocal
from app.domain.models import MetricaSistema
from app.domain.system_metrics import (
    collect_system_metrics_sample,
    list_system_metrics_history,
    record_system_metrics_sample,
)


def test_collect_system_metrics_sample_returns_four_nonnegative_fields():
    sample = collect_system_metrics_sample()
    assert set(sample.keys()) == {
        "cpu_percent",
        "memory_rss_mb",
        "memory_percent",
        "uptime_seconds",
    }
    for key, value in sample.items():
        assert isinstance(value, (int, float)), f"{key} não é numérico: {value!r}"
        assert value >= 0, f"{key} negativo: {value!r}"


def test_record_system_metrics_sample_inserts_a_row():
    with SessionLocal() as session:
        before = session.query(MetricaSistema).count()
        record_system_metrics_sample(session)
        after = session.query(MetricaSistema).count()
        assert after == before + 1


def test_list_system_metrics_history_returns_most_recent_in_ascending_order():
    with SessionLocal() as session:
        record_system_metrics_sample(session)
        record_system_metrics_sample(session)

        history = list_system_metrics_history(session, limit=2)

        assert len(history) == 2
        # ascendente: o segundo item é mais recente (ou igual) que o primeiro
        assert history[0]["coletado_em"] <= history[1]["coletado_em"]
        for row in history:
            assert set(row.keys()) == {
                "cpu_percent",
                "memory_rss_mb",
                "memory_percent",
                "uptime_seconds",
                "coletado_em",
            }
