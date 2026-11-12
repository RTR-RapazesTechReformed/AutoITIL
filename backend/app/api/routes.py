import hashlib
import json
import logging
from pathlib import Path
from typing import Literal

from fastapi import (
    APIRouter,
    File,
    Form,
    UploadFile,
)
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.classification.bert_classifier import BertClassifier
from app.classification.cascade import CascadeClassifier
from app.classification.classifier import Classifier
from app.config.settings import (
    BERT_N1_HUB_REPO,
    BERT_N2_HUB_REPO,
    ENRICHMENT_MODEL,
    MAX_ROWS,
    MAX_UPLOAD_BYTES,
    SUPPORTED_EXTENSIONS,
)
from app.domain.classification_metrics import (
    compute_throughput,
    list_classification_metrics_history,
    record_classification_metric,
)
from app.domain.db import SessionLocal
from app.domain.enrichment_metrics import (
    list_enrichment_metrics_history,
    record_enrichment_metric,
)
from app.domain.errors import IngestionError
from app.domain.ingestion_funnel import compute_ingestion_funnel
from app.domain.storage import (
    download_to_tempfile,
    get_bucket_name,
    object_exists,
    upload_bytes,
)
from app.domain.system_metrics import list_system_metrics_history
from app.domain.upload_history import (
    list_recent_uploads,
    mark_failed,
    mark_previewed,
    mark_tickets_generated,
    record_upload_received,
)
from app.enrichment.enricher import DescriptionEnricher
from app.evaluation.confusion import compute_confusion_matrices
from app.evaluation.enrichment_feedback import compute_feedback_summary
from app.evaluation.real_accuracy import compute_real_accuracy
from app.ingestion.pipeline import (
    IngestionPipeline,
)
from app.ingestion.reader import FileReader
from app.preprocessing.cleaner import TextCleaner
from app.tickets.exporter import export_tickets
from app.tickets.feedback import record_feedback
from app.tickets.generator import generate_ticket
from app.tickets.persistence import persist_generated_tickets
from app.tickets.priority_rules import PriorityRules
from app.tickets.queries import (
    MAX_PAGE_SIZE,
    dashboard_summary,
    export_tickets_rows,
    get_ticket_by_id,
    get_ticket_for_enrichment,
    list_tickets,
    save_enriched_description,
    tipo_area_heatmap,
    update_ticket_status,
    valid_status_codes,
)
from app.tickets.revisao import NIVEIS_VALIDOS, record_revisao

logger = logging.getLogger(__name__)


def _upload_history_storage_uri(file_key: str) -> str:
    return f"s3://{get_bucket_name()}/{file_key}"


def _record_upload_received(filename: str, content: bytes, file_key: str) -> None:
    try:
        with SessionLocal() as session:
            record_upload_received(
                session,
                nome_original=filename,
                extensao=Path(filename).suffix.lower(),
                hash_conteudo=hashlib.sha256(content).hexdigest(),
                tamanho_bytes=len(content),
                storage_uri=_upload_history_storage_uri(file_key),
            )
            session.commit()
    except Exception:
        logger.warning("upload_history_write_failed", exc_info=True)


def _mark_upload_previewed(file_key: str, total_linhas: int) -> None:
    try:
        with SessionLocal() as session:
            mark_previewed(session, _upload_history_storage_uri(file_key), total_linhas)
            session.commit()
    except Exception:
        logger.warning("upload_history_write_failed", exc_info=True)


def _mark_upload_failed(file_key: str, mensagem_erro: str) -> None:
    try:
        with SessionLocal() as session:
            mark_failed(session, _upload_history_storage_uri(file_key), mensagem_erro)
            session.commit()
    except Exception:
        logger.warning("upload_history_write_failed", exc_info=True)


def _mark_upload_tickets_generated(file_key: str) -> None:
    try:
        with SessionLocal() as session:
            mark_tickets_generated(session, _upload_history_storage_uri(file_key))
            session.commit()
    except Exception:
        logger.warning("upload_history_write_failed", exc_info=True)


METRICS_PATH = Path("data/processed/metrics_report.json")

_cleaner = TextCleaner()
_classifier = Classifier()
_bert_n1 = BertClassifier(
    model_dir=Path("models/bert/nivel1"), hub_repo_id=BERT_N1_HUB_REPO
)
_bert_n2 = BertClassifier(
    model_dir=Path("models/bert/nivel2"), hub_repo_id=BERT_N2_HUB_REPO
)
_cascade = CascadeClassifier(
    bert_n1=_bert_n1,
    bert_n2=_bert_n2,
    svm_fallback=_classifier,
)
_priority_rules = PriorityRules.from_json()
_enricher = DescriptionEnricher(model_name=ENRICHMENT_MODEL)


class ClassifyRequest(BaseModel):
    texto: str = Field(..., min_length=1)


class TicketRow(BaseModel):
    id: str = Field(..., min_length=1)
    descricao: str = Field(..., min_length=1)


class GenerateTicketsRequest(BaseModel):
    rows: list[TicketRow] = Field(..., min_length=1)
    format: Literal["json", "csv"] = "json"


class UpdateTicketStatusRequest(BaseModel):
    status: str = Field(..., min_length=1)


class ReviseTicketRequest(BaseModel):
    nivel: str = Field(..., min_length=1)
    valor: str = Field(..., min_length=1)


class FeedbackEnriquecimentoRequest(BaseModel):
    valor: str = Field(..., min_length=1)


router = APIRouter()

PREVIEW_ROWS = 5


def _safe_filename(filename):
    return Path(filename or "").name


def _generate_from_file_error(
    *, status_code: int, error_message: str, error_code: str
):
    """Erro de POST /api/tickets/generate-from-file. Sempre JSON — a rota é
    consumida exclusivamente pelo frontend React (generateTicketsFromFile
    em frontend/src/lib/api.ts), já que o fluxo legado em Jinja2 (que
    também batia nessa rota, esperando HTML) foi removido junto com a
    autenticação JWT."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {"code": error_code, "message": error_message},
        },
    )


def _json_success(message, data, status_code=200):
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data,
        },
    )


def _json_error(error, status_code=400):
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": getattr(
                    error,
                    "code",
                    "VALIDATION_ERROR",
                ),
                "message": str(error),
            },
        },
    )


def _dataframe_records(dataframe, limit=None):
    source = dataframe.head(limit) if limit else dataframe

    return json.loads(
        source.to_json(
            orient="records",
            date_format="iso",
            force_ascii=False,
        )
    )


def _suggestions_payload(suggestions):
    return [
        {
            "source_column": suggestion.source_column,
            "target_field": suggestion.target_field,
            "confidence": suggestion.confidence,
        }
        for suggestion in suggestions
    ]


def _suggested_mapping(suggestions):
    return {
        suggestion.target_field: suggestion.source_column for suggestion in suggestions
    }


def _preview_payload(filename, file_id, dataframe, suggestions):
    return {
        "file_id": file_id,
        "filename": filename,
        "row_count": len(dataframe),
        "column_count": len(dataframe.columns),
        "columns": list(dataframe.columns),
        "suggestions": _suggestions_payload(suggestions),
        "suggested_mapping": _suggested_mapping(suggestions),
        "preview_rows": _dataframe_records(
            dataframe,
            limit=PREVIEW_ROWS,
        ),
        "limits": {
            "max_rows": MAX_ROWS,
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "supported_extensions": SUPPORTED_EXTENSIONS,
        },
    }


async def _save_upload(file):
    filename = _safe_filename(file.filename)

    if not filename:
        raise IngestionError(
            "Nome de arquivo inválido.",
            code="INVALID_FILENAME",
        )

    FileReader.validate_extension(filename)

    content = await file.read()

    if len(content) > MAX_UPLOAD_BYTES:
        raise IngestionError(
            f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            code="FILE_TOO_LARGE",
        )

    try:
        file_id = upload_bytes(content, filename)
    except Exception as error:
        raise IngestionError(
            "Erro ao acessar o armazenamento de arquivos.",
            code="STORAGE_ERROR",
        ) from error

    # "uploaded_filename", não "filename" — "filename" já é um atributo
    # reservado de LogRecord; extra={"filename": ...} levantaria KeyError.
    # file_key é a mesma chave que "tickets_generated" loga mais abaixo —
    # permite juntar upload_saved e tickets_generated de requisições HTTP
    # diferentes, já que request_id não atravessa requisições distintas.
    logger.info(
        "upload_saved",
        extra={
            "uploaded_filename": filename,
            "size_bytes": len(content),
            "file_key": file_id,
        },
    )
    _record_upload_received(filename, content, file_id)
    return filename, file_id


def _resolve_upload_path(file_identifier):
    try:
        exists = object_exists(file_identifier)
    except Exception as error:
        raise IngestionError(
            "Erro ao acessar o armazenamento de arquivos.",
            code="STORAGE_ERROR",
        ) from error

    if not exists:
        raise IngestionError(
            "Arquivo enviado não foi encontrado.",
            code="FILE_NOT_FOUND",
        )

    try:
        return download_to_tempfile(file_identifier)
    except Exception as error:
        raise IngestionError(
            "Erro ao acessar o armazenamento de arquivos.",
            code="STORAGE_ERROR",
        ) from error


def _mapping_from_form(
    descricao,
    data,
    responsavel,
):
    mapping = {}

    if descricao:
        mapping[descricao] = "descricao"

    if data:
        mapping[data] = "data"

    if responsavel:
        mapping[responsavel] = "responsavel"

    return mapping


def _preview_upload(filename, file_id):
    local_path = download_to_tempfile(file_id)

    try:
        pipeline = IngestionPipeline()
        dataframe, suggestions = pipeline.preview(str(local_path))
    except Exception as error:
        mensagem_erro = (
            str(error)
            if isinstance(error, IngestionError)
            else "Falha ao pré-visualizar o arquivo."
        )
        _mark_upload_failed(file_id, mensagem_erro)
        raise
    finally:
        local_path.unlink(missing_ok=True)

    payload = _preview_payload(
        filename=filename,
        file_id=file_id,
        dataframe=dataframe,
        suggestions=suggestions,
    )
    _mark_upload_previewed(file_id, payload["row_count"])

    return (dataframe, suggestions, payload)


def _classify_dataframe(dataframe):
    """Classifica cada linha via CascadeClassifier (BERT N1→N2, fallback SVM),
    anexando categoria/área/confianças ao dataframe já limpo.
    """
    if not _cascade.is_available():
        return dataframe

    nivel1s, nivel2s, conf1s, conf2s = [], [], [], []
    for texto_limpo in dataframe["descricao_limpa"].fillna("").tolist():
        classification = _cascade.classify(texto_limpo) or {}
        nivel1s.append(classification.get("nivel1"))
        nivel2s.append(classification.get("nivel2"))
        conf1s.append(classification.get("confianca_n1"))
        conf2s.append(classification.get("confianca_n2"))

    dataframe["categoria"] = nivel1s
    dataframe["area_responsavel"] = nivel2s
    dataframe["confianca"] = conf1s
    dataframe["confianca_n2"] = conf2s
    return dataframe


@router.get("/api/health")
async def health_check():
    return {"status": "ok"}


@router.get("/api/models/quality")
async def api_get_metrics():
    if not METRICS_PATH.exists():
        return JSONResponse(content={"nivel1": {}, "nivel2": {}})

    report = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    return JSONResponse(content=report)


@router.get("/api/models/performance/system-history")
async def api_system_metrics_history(limit: int = 200):
    limit = max(1, min(limit, 1000))
    with SessionLocal() as session:
        data = list_system_metrics_history(session, limit=limit)
    return JSONResponse(content=data)


@router.get("/api/models/performance/enrichment-history")
async def api_enrichment_metrics_history(limit: int = 200):
    limit = max(1, min(limit, 1000))
    with SessionLocal() as session:
        data = list_enrichment_metrics_history(session, limit=limit)
    return JSONResponse(content=data)


@router.get("/api/models/performance/classification-history")
async def api_classification_metrics_history(limit: int = 200):
    """Telemetria do CascadeClassifier: uma entrada por (nível, arquitetura)
    de cada requisição de geração de tickets. Mesmo contrato de
    /api/models/performance/enrichment-history (lista pura, ordem cronológica)."""
    limit = max(1, min(limit, 1000))
    with SessionLocal() as session:
        data = list_classification_metrics_history(session, limit=limit)
    return JSONResponse(content=data)


@router.get("/api/operations/ingestion-funnel")
async def api_ingestion_funnel():
    """Funil do pipeline: uploads -> linhas -> tickets -> revisados ->
    enriquecidos. Cada etapa contada da própria tabela, então a diferença
    entre elas é exatamente o volume perdido no caminho."""
    with SessionLocal() as session:
        data = compute_ingestion_funnel(session)
    return JSONResponse(content=data)


@router.get("/api/operations/type-area")
async def api_tipo_area_heatmap():
    """Grade tipo ITIL x área responsável: volume e confiança média do
    Nível 2 em cada cruzamento. As barras do dashboard mostram as marginais;
    esta rota mostra onde elas se encontram."""
    with SessionLocal() as session:
        data = tipo_area_heatmap(session)
    return JSONResponse(content=data)


@router.get("/api/models/quality/confusion-matrix")
async def api_confusion_matrix():
    """Matriz de confusão por nível, sobre as revisões humanas: o que o
    modelo previu (original) contra o que o humano corrigiu (revisado)."""
    with SessionLocal() as session:
        data = compute_confusion_matrices(session)
    return JSONResponse(content=data)


@router.get("/api/models/performance/throughput")
async def api_throughput():
    """Vazão e custo de CPU por chamado, por nível do classificador."""
    with SessionLocal() as session:
        data = compute_throughput(session)
    return JSONResponse(content=data)


@router.get("/api/models/quality/reviews")
async def api_real_accuracy():
    with SessionLocal() as session:
        data = compute_real_accuracy(session)

    return JSONResponse(content=data)


@router.get("/api/models/quality/enrichment-feedback")
async def api_enrichment_feedback_summary():
    with SessionLocal() as session:
        data = compute_feedback_summary(session)

    return JSONResponse(content=data)


@router.get("/api/operations/summary")
async def api_dashboard_summary():
    with SessionLocal() as session:
        data = dashboard_summary(session)

    return JSONResponse(content={"success": True, "data": data})


@router.get("/api/uploads")
async def api_list_uploads():
    with SessionLocal() as session:
        uploads = list_recent_uploads(session)
    return _json_success("Histórico de uploads.", uploads)


@router.get("/api/tickets")
async def api_list_tickets(
    page: int = 1,
    page_size: int = 20,
    area: str | None = None,
    prioridade: str | None = None,
    status: str | None = None,
    busca: str | None = None,
):
    if page < 1:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "page deve ser >= 1.",
                },
            },
        )

    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"page_size deve estar entre 1 e {MAX_PAGE_SIZE}.",
                },
            },
        )

    with SessionLocal() as session:
        if status is not None:
            validos = valid_status_codes(session)
            if status not in validos:
                return JSONResponse(
                    status_code=422,
                    content={
                        "success": False,
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": (
                                f"status inválido: '{status}'. "
                                f"Use um dos: {', '.join(validos)}."
                            ),
                        },
                    },
                )

        data = list_tickets(
            session,
            page=page,
            page_size=page_size,
            area=area,
            prioridade=prioridade,
            status=status,
            busca=busca,
        )

    return JSONResponse(content={"success": True, "data": data})


@router.get("/api/tickets/export")
async def api_export_tickets(
    format: Literal["csv", "xlsx"] = "csv",
    area: str | None = None,
    prioridade: str | None = None,
    status: str | None = None,
    busca: str | None = None,
):
    if status is not None:
        with SessionLocal() as session:
            validos = valid_status_codes(session)
            if status not in validos:
                return JSONResponse(
                    status_code=422,
                    content={
                        "success": False,
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": (
                                f"status inválido: '{status}'. "
                                f"Use um dos: {', '.join(validos)}."
                            ),
                        },
                    },
                )

    with SessionLocal() as session:
        rows = export_tickets_rows(
            session, area=area, prioridade=prioridade, status=status, busca=busca
        )

    content = export_tickets(rows, format=format)
    media_type = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }[format]
    filename = f"tickets-classificados.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/api/tickets/{ticket_id}")
async def api_update_ticket_status(ticket_id: int, payload: UpdateTicketStatusRequest):
    with SessionLocal() as session:
        validos = valid_status_codes(session)
        if payload.status not in validos:
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": (
                            f"status inválido: '{payload.status}'. "
                            f"Use um dos: {', '.join(validos)}."
                        ),
                    },
                },
            )

        result = update_ticket_status(session, ticket_id, payload.status)
        if result is None:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": {
                        "code": "TICKET_NOT_FOUND",
                        "message": f"Ticket com id {ticket_id} não encontrado.",
                    },
                },
            )

        session.commit()

    return JSONResponse(
        content={"success": True, "message": "Ticket atualizado.", "data": result}
    )


@router.patch("/api/tickets/{ticket_id}/revisao")
async def api_revise_ticket_classification(ticket_id: int, payload: ReviseTicketRequest):
    if payload.nivel not in NIVEIS_VALIDOS:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": (
                        f"nivel inválido: '{payload.nivel}'. "
                        f"Use um dos: {', '.join(NIVEIS_VALIDOS)}."
                    ),
                },
            },
        )

    with SessionLocal() as session:
        try:
            resultado = record_revisao(session, ticket_id, payload.nivel, payload.valor)
        except ValueError as exc:
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "error": {"code": "VALIDATION_ERROR", "message": str(exc)},
                },
            )

        if resultado is None:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": {
                        "code": "TICKET_NOT_FOUND",
                        "message": f"Ticket com id {ticket_id} não encontrado.",
                    },
                },
            )

        session.commit()
        ticket_atualizado = get_ticket_by_id(session, ticket_id)

    return JSONResponse(
        content={
            "success": True,
            "message": "Revisão registrada.",
            "data": ticket_atualizado,
        }
    )


@router.patch("/api/tickets/{ticket_id}/feedback-enriquecimento")
async def api_feedback_enriquecimento(ticket_id: int, payload: FeedbackEnriquecimentoRequest):
    with SessionLocal() as session:
        try:
            resultado = record_feedback(session, ticket_id, payload.valor)
        except ValueError as exc:
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "error": {"code": "VALIDATION_ERROR", "message": str(exc)},
                },
            )

        if resultado is None:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": {
                        "code": "TICKET_NOT_FOUND",
                        "message": f"Ticket com id {ticket_id} não encontrado.",
                    },
                },
            )

        session.commit()
        ticket_atualizado = get_ticket_by_id(session, ticket_id)

    return JSONResponse(
        content={
            "success": True,
            "message": "Feedback registrado.",
            "data": ticket_atualizado,
        }
    )


@router.post("/api/tickets/{ticket_id}/enrich")
async def api_enrich_ticket(ticket_id: int):
    """F2-4 — reescreve a descrição original do ticket via LLM pequeno, sob
    demanda (nunca em lote — ver comentário em app.enrichment.enricher).
    Idempotente: se já existe uma versão em cache, devolve ela sem chamar o
    modelo de novo."""
    logger.info("enrich_requested", extra={"ticket_id": ticket_id})

    with SessionLocal() as session:
        found = get_ticket_for_enrichment(session, ticket_id)
        if found is None:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": {
                        "code": "TICKET_NOT_FOUND",
                        "message": f"Ticket com id {ticket_id} não encontrado.",
                    },
                },
            )

        if found["descricao_enriquecida"] is not None:
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Descrição já enriquecida anteriormente (cache).",
                    "data": {
                        "id": ticket_id,
                        "descricao_enriquecida": found["descricao_enriquecida"],
                    },
                }
            )

        if not _enricher.is_available():
            logger.warning(
                "enrich_failed",
                extra={"ticket_id": ticket_id, "reason": "model_unavailable"},
            )
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": {
                        "code": "ENRICHMENT_UNAVAILABLE",
                        "message": (
                            f"Modelo de enriquecimento ({ENRICHMENT_MODEL}) "
                            "indisponível no momento (sem rede para baixar do "
                            "Hub, ou falha ao carregar)."
                        ),
                    },
                },
            )

        descricao_enriquecida = _enricher.enrich(found["descricao_original"])
        if descricao_enriquecida is None:
            logger.warning(
                "enrich_failed",
                extra={"ticket_id": ticket_id, "reason": "generation_failed"},
            )
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": {
                        "code": "ENRICHMENT_UNAVAILABLE",
                        "message": "Falha ao gerar a descrição enriquecida.",
                    },
                },
            )

        result = save_enriched_description(session, ticket_id, descricao_enriquecida)
        session.commit()

        try:
            record_enrichment_metric(
                session,
                ticket_id=ticket_id,
                duracao_ms=_enricher.last_call_duration_ms,
                tokens_entrada=_enricher.last_call_tokens_entrada,
                tokens_saida=_enricher.last_call_tokens_saida,
            )
            session.commit()
        except Exception:
            session.rollback()
            logger.warning("enrichment_metric_write_failed", exc_info=True)

    logger.info("enrich_succeeded", extra={"ticket_id": ticket_id})
    return JSONResponse(
        content={
            "success": True,
            "message": "Descrição enriquecida com sucesso.",
            "data": result,
        }
    )


@router.post("/api/upload")
async def api_upload_file(
    file: UploadFile = File(...),
):
    try:
        filename, file_id = await _save_upload(file)
        _, _, payload = _preview_upload(
            filename,
            file_id,
        )

    except IngestionError as error:
        return _json_error(error)

    return _json_success(
        "Arquivo lido com sucesso.",
        payload,
    )


@router.post("/api/process")
async def api_process_file(
    file_id: str = Form(...),
    descricao: str = Form(...),
    data: str = Form(""),
    responsavel: str = Form(""),
):
    resolved_file_path = None

    try:
        resolved_file_path = _resolve_upload_path(file_id)
        mapping = _mapping_from_form(
            descricao,
            data,
            responsavel,
        )

        pipeline = IngestionPipeline()
        result = pipeline.execute(
            str(resolved_file_path),
            mapping=mapping,
        )

        result = _cleaner.clean_dataframe(result, col="descricao")
        result = _classify_dataframe(result)

    except IngestionError as error:
        return _json_error(error)
    finally:
        if resolved_file_path is not None:
            resolved_file_path.unlink(missing_ok=True)

    return _json_success(
        "Arquivo processado com sucesso.",
        {
            "file_id": file_id,
            "filename": Path(file_id).name,
            "row_count": len(result),
            "model_trained": _cascade.is_available(),
            "mapping": mapping,
            "records": _dataframe_records(result),
        },
    )


def _acumular_metricas_classificacao(acumulador: dict, metricas: list[dict]) -> None:
    """Soma a telemetria de UMA classificação no acumulador da requisição.

    A rota classifica linha a linha, então um upload de 5000 linhas geraria
    10.000 linhas de métrica (2 níveis x 5000) se cada chamada virasse um
    INSERT. Agregamos por (nível, arquitetura) e gravamos uma linha por
    grupo no fim — `itens` acumula quantas linhas entraram, preservando o
    custo por chamado em duracao_ms/itens.
    """
    for m in metricas:
        chave = (m["nivel"], m["arquitetura"])
        alvo = acumulador.setdefault(
            chave, {"duracao_ms": 0.0, "tokens_entrada": 0, "itens": 0}
        )
        alvo["duracao_ms"] += m["duracao_ms"]
        alvo["tokens_entrada"] += m["tokens_entrada"]
        alvo["itens"] += m["itens"]


def _persistir_metricas_classificacao(session, acumulador: dict) -> None:
    """Grava o acumulado. Telemetria nunca derruba a requisição: um erro
    aqui é engolido, porque perder a métrica é preferível a perder os
    tickets que acabaram de ser classificados."""
    try:
        for (nivel, arquitetura), v in acumulador.items():
            if v["itens"] <= 0:
                continue
            record_classification_metric(
                session,
                nivel=nivel,
                arquitetura=arquitetura,
                duracao_ms=round(v["duracao_ms"], 3),
                tokens_entrada=v["tokens_entrada"],
                itens=v["itens"],
            )
    except Exception:  # noqa: BLE001 - telemetria e best-effort
        logger.exception("falha ao persistir metrica_classificacao")


@router.post("/api/tickets/generate-from-file")
async def generate_tickets_from_file(
    file_path: str = Form(...),
    descricao: str = Form(...),
    data: str = Form(""),
    responsavel: str = Form(""),
    format: str = Form("json"),
):
    """Gera, persiste no Postgres e baixa os tickets a partir de um arquivo
    já enviado e mapeado (mesmos hidden fields usados por /process),
    reaproveitando o pipeline de ingestão + o CascadeClassifier +
    generate_ticket/export_tickets/persist_generated_tickets."""
    resolved_file_path = None
    tamanho_bytes = None

    try:
        resolved_file_path = _resolve_upload_path(file_path)
        tamanho_bytes = resolved_file_path.stat().st_size
        mapping = _mapping_from_form(descricao, data, responsavel)

        pipeline = IngestionPipeline()
        result = pipeline.execute(str(resolved_file_path), mapping=mapping)
        result = _cleaner.clean_dataframe(result, col="descricao")

    except IngestionError as error:
        _mark_upload_failed(file_path, str(error))
        return _generate_from_file_error(
            status_code=400,
            error_message=str(error),
            error_code=error.code,
        )
    finally:
        if resolved_file_path is not None:
            resolved_file_path.unlink(missing_ok=True)

    if not _cascade.is_available():
        _mark_upload_failed(
            file_path, "Nenhum classificador disponível para gerar os tickets."
        )
        return _generate_from_file_error(
            status_code=503,
            error_message="Nenhum classificador disponível para gerar os tickets.",
            error_code="CLASSIFIER_UNAVAILABLE",
        )

    tickets = []
    persistence_rows = []
    metricas_classificacao: dict = {}
    for idx, row in enumerate(result.itertuples(index=False), start=1):
        classification = _cascade.classify(str(row.descricao_limpa))
        _acumular_metricas_classificacao(
            metricas_classificacao, _cascade.last_call_metrics
        )
        ticket = generate_ticket(
            row={"id": f"L{idx:04d}", "descricao": str(row.descricao)},
            classification=classification,
            rules=_priority_rules,
            ticket_counter=idx,
        )
        tickets.append(ticket)
        persistence_rows.append(
            {
                "linha_origem": idx,
                "descricao_original": str(row.descricao),
                "descricao_limpa": str(row.descricao_limpa),
                "data": getattr(row, "data", None),
                "responsavel": getattr(row, "responsavel", None),
                "classification": classification,
                "prioridade_codigo": ticket["prioridade"],
                "titulo_sugerido": ticket["titulo_sugerido"],
            }
        )

    try:
        with SessionLocal() as session:
            created = persist_generated_tickets(
                session,
                file_key=file_path,
                bucket=get_bucket_name(),
                tamanho_bytes=tamanho_bytes,
                rows=persistence_rows,
            )
            _persistir_metricas_classificacao(session, metricas_classificacao)
            session.commit()
    except IngestionError as error:
        _mark_upload_failed(file_path, str(error))
        return _generate_from_file_error(
            status_code=400,
            error_message=str(error),
            error_code=error.code,
        )
    except Exception as error:
        # Erro genérico de persistência não vira nunca IngestionError, então
        # sem isso a causa real ficava só em db_error.__cause__ (nunca
        # logada) — foi assim que achamos o bug real de NaN em data vazia
        # (ver app/tickets/persistence.py::_none_if_missing): sem esse log,
        # o servidor não tinha nenhum rastro do que quebrou.
        logger.exception("Falha ao persistir tickets no banco (DB_ERROR)")
        db_error = IngestionError(
            "Falha ao persistir tickets no banco.", code="DB_ERROR"
        )
        db_error.__cause__ = error
        _mark_upload_failed(file_path, str(db_error))
        return _generate_from_file_error(
            status_code=400,
            error_message=str(db_error),
            error_code=db_error.code,
        )

    _mark_upload_tickets_generated(file_path)

    # Substitui o id_ticket gerado localmente (contador por request, não
    # globalmente único) pelo codigo real atribuído pela sequence do banco
    # — assim o código no arquivo baixado é o mesmo que aparece no Kanban.
    for ticket, persisted in zip(tickets, created, strict=True):
        ticket["id_ticket"] = persisted["codigo"]

    logger.info(
        "tickets_generated",
        extra={"file_key": file_path, "total_tickets": len(created)},
    )

    content = export_tickets(tickets, format=format)
    media_type = "application/json" if format == "json" else "text/csv"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="tickets.{format}"'},
    )


@router.post("/api/classify")
def classify(payload: ClassifyRequest) -> JSONResponse:
    if not _cascade.is_available():
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Classificador indisponível: nenhum modelo treinado encontrado."
            },
        )

    texto_limpo = _cleaner.clean(payload.texto)
    resultado = _cascade.classify(texto_limpo)
    return JSONResponse(content=resultado)


@router.post("/api/tickets/generate")
def generate_tickets(payload: GenerateTicketsRequest) -> Response:
    if not _cascade.is_available():
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Classificador indisponível: nenhum modelo treinado encontrado."
            },
        )

    tickets = []
    for idx, row in enumerate(payload.rows, start=1):
        texto_limpo = _cleaner.clean(row.descricao)
        classification = _cascade.classify(texto_limpo)
        ticket = generate_ticket(
            row={"id": row.id, "descricao": row.descricao},
            classification=classification,
            rules=_priority_rules,
            ticket_counter=idx,
        )
        tickets.append(ticket)

    content = export_tickets(tickets, format=payload.format)
    media_type = "application/json" if payload.format == "json" else "text/csv"
    filename = f"tickets.{payload.format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


