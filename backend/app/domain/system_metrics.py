"""system_metrics.py — amostras periódicas de CPU/memória do processo do
backend (tabela `metrica_sistema`), coletadas por uma tarefa em background
iniciada em app.main (ver lifespan).

collect_system_metrics_sample() é uma função pura (não grava no banco),
separada de record_system_metrics_sample() pra poder testar a leitura via
psutil sem precisar de sessão de banco."""

from __future__ import annotations

import os
import time

import psutil
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import MetricaSistema

# Process de módulo, não recriado a cada coleta: cpu_percent(interval=None)
# calcula a média de CPU DESDE A CHAMADA ANTERIOR NO MESMO OBJETO, e um
# Process novo não tem chamada anterior (retornaria sempre 0.0).
_PROCESS = psutil.Process(os.getpid())
_PROCESS.cpu_percent(interval=None)  # baseline; a 1a leitura real vem depois


def collect_system_metrics_sample() -> dict[str, float]:
    """Uma amostra de CPU/memória do processo do backend.

    cpu_percent é a MÉDIA desde a amostra anterior (interval=None sobre um
    Process persistente), não uma espiada instantânea.

    Antes usávamos interval=0.1, que mede uma janela de 100ms. Com o loop
    coletando a cada 60s, isso observava 0,17% do tempo — e como o backend
    fica ocioso entre uploads, a leitura era 0,0 quase sempre: uma rajada de
    ~1,5s de classificação praticamente nunca caía dentro da janelinha.
    Medido: 1,5s de trabalho numa janela de 4s dá 0,0% com interval=0.1 e
    36,5% com a média da janela.

    Consequência a ter em mente ao ler o gráfico: o valor é a média do
    intervalo, então uma rajada curta aparece diluída (1,5s a 100% em 60s
    ≈ 2,5%), não como um pico de 100%. É o comportamento correto para
    dimensionar infraestrutura — é o que vai alimentar o cálculo de custo
    depois — mas não serve para achar o pico instantâneo.
    """
    process = _PROCESS
    cpu_percent = process.cpu_percent(interval=None)
    memory_info = process.memory_info()
    return {
        "cpu_percent": cpu_percent,
        "memory_rss_mb": memory_info.rss / (1024 * 1024),
        "memory_percent": process.memory_percent(),
        "uptime_seconds": time.time() - process.create_time(),
    }


def record_system_metrics_sample(session: Session) -> None:
    sample = collect_system_metrics_sample()
    session.add(MetricaSistema(**sample))
    session.commit()


def list_system_metrics_history(session: Session, limit: int = 200) -> list[dict]:
    """Devolve as últimas `limit` amostras, em ordem cronológica ASCENDENTE
    (mais antiga primeiro) — pronto pra plotar como série temporal.

    Implementação: busca as últimas `limit` em ordem DESCENDENTE (pra pegar
    as mais recentes de fato, não as mais antigas do banco todo) e inverte
    a lista em Python antes de devolver."""
    rows = session.scalars(
        select(MetricaSistema)
        .order_by(MetricaSistema.coletado_em.desc(), MetricaSistema.id.desc())
        .limit(limit)
    ).all()
    rows = list(reversed(rows))
    return [
        {
            "cpu_percent": float(row.cpu_percent),
            "memory_rss_mb": float(row.memory_rss_mb),
            "memory_percent": float(row.memory_percent),
            "uptime_seconds": float(row.uptime_seconds),
            "coletado_em": row.coletado_em.isoformat(),
        }
        for row in rows
    ]
