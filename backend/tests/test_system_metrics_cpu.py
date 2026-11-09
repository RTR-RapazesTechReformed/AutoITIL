"""Regressão da amostragem de CPU.

O coletor lia cpu_percent(interval=0.1) num psutil.Process recriado a cada
chamada. Com o loop rodando a cada 60s, isso observava 0,17% do tempo e
reportava 0,0 quase sempre — as rajadas de classificação caíam fora da
janela. Agora é a média desde a amostra anterior, num Process persistente.
"""

from __future__ import annotations

import threading
import time

from app.domain import system_metrics


def _queimar_cpu(segundos: float) -> None:
    fim = time.time() + segundos
    while time.time() < fim:
        pass


def test_amostra_tem_as_chaves_esperadas():
    amostra = system_metrics.collect_system_metrics_sample()
    assert set(amostra) == {
        "cpu_percent",
        "memory_rss_mb",
        "memory_percent",
        "uptime_seconds",
    }
    assert amostra["memory_rss_mb"] > 0
    assert amostra["uptime_seconds"] > 0


def test_usa_process_persistente():
    """Um Process novo a cada coleta zeraria a média — interval=None depende
    de haver uma chamada anterior no MESMO objeto."""
    assert system_metrics._PROCESS is not None
    primeiro = system_metrics._PROCESS
    system_metrics.collect_system_metrics_sample()
    assert system_metrics._PROCESS is primeiro


def test_cpu_registra_trabalho_ocorrido_entre_amostras():
    """O ponto do bug: trabalho que acontece ENTRE duas amostras precisa
    aparecer, mesmo que o processo esteja ocioso no instante da leitura."""
    system_metrics.collect_system_metrics_sample()  # baseline

    t = threading.Thread(target=_queimar_cpu, args=(0.5,))
    t.start()
    t.join()
    time.sleep(0.3)  # ocioso na hora da leitura, como na vida real

    amostra = system_metrics.collect_system_metrics_sample()
    assert amostra["cpu_percent"] > 0, (
        "CPU zerada apesar de 0,5s de trabalho na janela — a amostragem "
        "voltou a ser instantânea"
    )
