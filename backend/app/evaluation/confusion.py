"""confusion.py — matriz de confusão das revisões humanas.

Irmã de real_accuracy.py: mesma fonte (`revisao_classificacao`), mesma
semântica de y_pred/y_true (original = o que o modelo disse, revisado = o
que o humano corrigiu). A diferença é o recorte: real_accuracy responde
QUANTO o modelo erra; esta responde ONDE — quais classes ele troca entre
si, que é o que orienta retreino.

Sem scikit-learn aqui de propósito: a matriz é uma contagem simples de
pares, e o formato que o frontend precisa (lista de células com rótulos)
não é o ndarray que confusion_matrix devolve. Trazer sklearn só para
depois desmontar o array custaria mais código, não menos.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import AreaResponsavel, RevisaoClassificacao, TipoItil


def _matriz(session: Session, coluna_original, coluna_revisada, modelo_rotulo) -> dict:
    rows = session.execute(
        select(coluna_original, coluna_revisada).where(
            coluna_original.is_not(None),
            coluna_revisada.is_not(None),
        )
    ).all()

    nomes = dict(session.execute(select(modelo_rotulo.id, modelo_rotulo.nome)).all())
    # Todos os rótulos do domínio, não só os que apareceram: uma matriz que
    # muda de tamanho conforme o volume de revisões é ilegível, e a ausência
    # de uma classe é informação (ninguém classificou nada como "Problema").
    rotulos = [nomes[k] for k in sorted(nomes)]

    contagem = Counter(
        (nomes[original], nomes[revisado]) for original, revisado in rows
    )

    celulas = [
        {
            "predito": predito,
            "real": real,
            "total": contagem.get((predito, real), 0),
            # Acerto = o humano confirmou o que o modelo disse.
            "acerto": predito == real,
        }
        for predito in rotulos
        for real in rotulos
    ]

    acertos = sum(c["total"] for c in celulas if c["acerto"])
    total = sum(c["total"] for c in celulas)

    return {
        "rotulos": rotulos,
        "celulas": celulas,
        "total_revisado": total,
        "acertos": acertos,
        "acuracia": round(acertos / total, 4) if total else None,
    }


def compute_confusion_matrices(session: Session) -> dict:
    """Uma matriz por nível. `celulas` vem densa (todas as combinações de
    rótulos, inclusive zeros) para o frontend poder desenhar o heatmap sem
    precisar preencher buracos."""
    return {
        "nivel1": _matriz(
            session,
            RevisaoClassificacao.tipo_itil_original_id,
            RevisaoClassificacao.tipo_itil_revisado_id,
            TipoItil,
        ),
        "nivel2": _matriz(
            session,
            RevisaoClassificacao.area_original_id,
            RevisaoClassificacao.area_revisado_id,
            AreaResponsavel,
        ),
    }
