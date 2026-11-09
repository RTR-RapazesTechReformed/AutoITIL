"""classification_metrics.py — histórico de tempo/tokens de cada chamada
BEM-SUCEDIDA do CascadeClassifier (tabela `metrica_classificacao`).

Irmã de app.domain.enrichment_metrics, com uma diferença deliberada de
granularidade: lá é uma linha por ticket enriquecido (o Gemma roda sob
demanda, um por vez); aqui é uma linha por CHAMADA do classificador, porque
predict_batch() processa até MAX_ROWS (5000) textos numa passada só. Gravar
uma linha por ticket faria a ingestão emitir milhares de INSERTs disputando
a mesma transação que grava os tickets. `itens` guarda o tamanho do lote,
então duracao_ms/itens continua dando o custo por chamado.

Sem FK para nada — é telemetria, não deve bloquear nem cascatear.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import MetricaClassificacao


def record_classification_metric(
    session: Session,
    *,
    nivel: int,
    arquitetura: str,
    duracao_ms: float,
    tokens_entrada: int,
    itens: int = 1,
) -> None:
    session.add(
        MetricaClassificacao(
            nivel=nivel,
            arquitetura=arquitetura,
            duracao_ms=duracao_ms,
            tokens_entrada=tokens_entrada,
            itens=itens,
        )
    )
    session.flush()


def list_classification_metrics_history(
    session: Session, limit: int = 200
) -> list[dict]:
    """Últimas `limit` chamadas em ordem cronológica ASCENDENTE (mais antiga
    primeiro) — mesma técnica de app.domain.system_metrics e
    app.domain.enrichment_metrics: busca DESC no banco, inverte em Python."""
    rows = session.scalars(
        select(MetricaClassificacao)
        .order_by(
            MetricaClassificacao.criado_em.desc(), MetricaClassificacao.id.desc()
        )
        .limit(limit)
    ).all()
    rows = list(reversed(rows))
    return [
        {
            "nivel": row.nivel,
            "arquitetura": row.arquitetura,
            "duracao_ms": float(row.duracao_ms),
            "tokens_entrada": row.tokens_entrada,
            "itens": row.itens,
            # Custo unitário já dividido: o gráfico compara chamadas de lotes
            # muito diferentes (1 texto no /classify avulso, 5000 na ingestão),
            # e duracao_ms cru tornaria as duas incomparáveis.
            "duracao_ms_por_item": round(float(row.duracao_ms) / row.itens, 3),
            "criado_em": row.criado_em.isoformat(),
        }
        for row in rows
    ]


def compute_throughput(session: Session) -> dict:
    """Vazão e custo de CPU por chamado, agregados por nível.

    duracao_ms é o tempo somado de todas as chamadas daquele nível, e itens
    o total de chamados que passaram por ele. A divisão é feita no SQL sobre
    as SOMAS, não a média das médias: lotes têm tamanhos muito diferentes
    (1 chamado numa classificação avulsa, 15 numa ingestão), e a média de
    médias daria o mesmo peso a lotes desiguais.

    `chamados_por_minuto` é a vazão sustentada do modelo — quanto ele
    processaria em um minuto de CPU contínua, não incluindo I/O, banco nem
    espera de rede. É o número que serve de base para dimensionar
    infraestrutura (e, depois, custo).
    """
    rows = session.execute(
        select(
            MetricaClassificacao.nivel,
            MetricaClassificacao.arquitetura,
            func.sum(MetricaClassificacao.duracao_ms),
            func.sum(MetricaClassificacao.tokens_entrada),
            func.sum(MetricaClassificacao.itens),
            func.count(MetricaClassificacao.id),
        ).group_by(MetricaClassificacao.nivel, MetricaClassificacao.arquitetura)
        .order_by(MetricaClassificacao.nivel)
    ).all()

    niveis = []
    ms_total_por_chamado = 0.0
    for nivel, arquitetura, soma_ms, soma_tokens, soma_itens, chamadas in rows:
        soma_ms = float(soma_ms or 0)
        soma_itens = int(soma_itens or 0)
        if soma_itens <= 0:
            continue
        ms_por_chamado = soma_ms / soma_itens
        ms_total_por_chamado += ms_por_chamado
        niveis.append(
            {
                "nivel": nivel,
                "arquitetura": arquitetura,
                "chamadas": chamadas,
                "chamados": soma_itens,
                "ms_por_chamado": round(ms_por_chamado, 3),
                "tokens_por_chamado": round(float(soma_tokens or 0) / soma_itens, 2),
                "chamados_por_minuto": round(60_000 / ms_por_chamado, 1),
            }
        )

    return {
        "niveis": niveis,
        # Somado, não pela média: um chamado atravessa N1 E N2, então o custo
        # total por chamado é a soma dos níveis, não a média deles.
        "ms_por_chamado_total": round(ms_total_por_chamado, 3),
        "chamados_por_minuto_total": (
            round(60_000 / ms_total_por_chamado, 1) if ms_total_por_chamado else None
        ),
    }
