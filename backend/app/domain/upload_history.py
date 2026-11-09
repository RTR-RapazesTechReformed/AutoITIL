"""upload_history.py — histórico de uploads, pra rastreabilidade de todo
arquivo enviado (não só os que viram tickets).

historico_upload é independente de arquivo/registro/ticket (sem FK) —
cada upload ganha uma linha aqui em 'recebido', que evolui pra
'pre_visualizado' -> 'tickets_gerados', ou 'falhou' em qualquer etapa.
Uploads abandonados simplesmente ficam parados num estado não-terminal —
não há job de limpeza/expiração aqui.

Correlação entre chamadas da mesma tentativa é feita por storage_uri
(não por um id explícito — não há threading de id entre as requisições
HTTP do fluxo de upload -> preview -> geração), buscando sempre a linha
aberta (status 'recebido' ou 'pre_visualizado') mais recente. Funções
mark_* nunca lançam se nenhuma linha aberta for encontrada — degradam
graciosamente, mesmo contrato de "não travar o fluxo principal" que os
chamadores em app.api.routes também seguem."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import HistoricoUpload

_OPEN_STATUSES = ("recebido", "pre_visualizado")


def record_upload_received(
    session: Session,
    *,
    nome_original: str,
    extensao: str,
    hash_conteudo: str,
    tamanho_bytes: int,
    storage_uri: str,
) -> int:
    """Insere uma linha nova com status='recebido'. Devolve o id criado."""
    entry = HistoricoUpload(
        nome_original=nome_original,
        extensao=extensao,
        hash_conteudo=hash_conteudo,
        tamanho_bytes=tamanho_bytes,
        storage_uri=storage_uri,
        status="recebido",
    )
    session.add(entry)
    session.flush()
    return entry.id


def _find_open_entry(session: Session, storage_uri: str) -> HistoricoUpload | None:
    return session.scalars(
        select(HistoricoUpload)
        .where(
            HistoricoUpload.storage_uri == storage_uri,
            HistoricoUpload.status.in_(_OPEN_STATUSES),
        )
        .order_by(HistoricoUpload.criado_em.desc(), HistoricoUpload.id.desc())
        .limit(1)
    ).first()


def mark_previewed(session: Session, storage_uri: str, total_linhas: int) -> None:
    """Atualiza a linha aberta mais recente pra 'pre_visualizado'."""
    entry = _find_open_entry(session, storage_uri)
    if entry is None:
        return
    entry.status = "pre_visualizado"
    entry.total_linhas = total_linhas


def mark_failed(session: Session, storage_uri: str, mensagem_erro: str) -> None:
    """Atualiza a linha aberta mais recente pra 'falhou'."""
    entry = _find_open_entry(session, storage_uri)
    if entry is None:
        return
    entry.status = "falhou"
    entry.mensagem_erro = mensagem_erro


def mark_tickets_generated(session: Session, storage_uri: str) -> None:
    """Atualiza a linha aberta mais recente pra 'tickets_gerados'."""
    entry = _find_open_entry(session, storage_uri)
    if entry is None:
        return
    entry.status = "tickets_gerados"


def list_recent_uploads(session: Session, limit: int = 50) -> list[dict]:
    """Devolve as últimas `limit` linhas, mais recentes primeiro."""
    entries = session.scalars(
        select(HistoricoUpload)
        .order_by(HistoricoUpload.criado_em.desc(), HistoricoUpload.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": entry.id,
            "nome_original": entry.nome_original,
            "tamanho_bytes": entry.tamanho_bytes,
            "status": entry.status,
            "total_linhas": entry.total_linhas,
            "mensagem_erro": entry.mensagem_erro,
            "criado_em": entry.criado_em.isoformat(),
            "atualizado_em": entry.atualizado_em.isoformat(),
        }
        for entry in entries
    ]
