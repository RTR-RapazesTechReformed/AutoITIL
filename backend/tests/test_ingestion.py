"""Testes do pipeline de ingestão (upload S3 + leitura/mapeamento/validação).

Requer o container do MinIO do docker-compose.yml rodando (`docker compose up -d`) —
os testes fazem upload real via `app.domain.storage.upload_bytes`, sem mockar boto3.
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.domain.storage import upload_bytes
from app.ingestion.mapper import SemanticMapper, detect_columns
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.reader import FileReader
from app.ingestion.validator import MappingValidator
from app.main import app
from tests.auth_helpers import AUTH_HEADERS


def _write_csv(path, dataframe):
    dataframe.to_csv(path, index=False)


def _write_xlsx(path, dataframe):
    dataframe.to_excel(path, index=False)


def _stage_csv_in_s3(tmp_path, name, dataframe):
    local_path = tmp_path / name
    _write_csv(local_path, dataframe)
    content = local_path.read_bytes()
    return upload_bytes(content, name)


def test_file_reader_accepts_csv_and_xlsx(tmp_path):
    dataframe = pd.DataFrame(
        {
            "descricao": ["Falha no login"],
            "data": ["2026-05-14"],
            "responsavel": ["Ana"],
        }
    )

    csv_path = tmp_path / "amostra.csv"
    xlsx_path = tmp_path / "amostra.xlsx"

    _write_csv(csv_path, dataframe)
    _write_xlsx(xlsx_path, dataframe)

    csv_result = FileReader.read(csv_path)
    xlsx_result = FileReader.read(xlsx_path)

    assert list(csv_result.columns) == ["descricao", "data", "responsavel"]
    assert list(xlsx_result.columns) == ["descricao", "data", "responsavel"]


@pytest.mark.parametrize(
    ("filename", "dataframe", "expected_columns"),
    [
        (
            "layout_exato.csv",
            pd.DataFrame(
                {
                    "descricao": ["Falha no login"],
                    "data": ["2026-05-14"],
                    "responsavel": ["Ana"],
                }
            ),
            ["descricao", "data", "responsavel"],
        ),
        (
            "layout_alias.xlsx",
            pd.DataFrame(
                {
                    "titulo": ["Falha no servidor de arquivos"],
                    "dt_ocorrencia": ["14/05/2026"],
                    "tecnico_responsavel": ["Carlos"],
                }
            ),
            ["titulo", "dt_ocorrencia", "tecnico_responsavel"],
        ),
        (
            "layout_colunas_extras.csv",
            pd.DataFrame(
                {
                    "problema": ["Lentidão no ERP"],
                    "abertura": ["2026-05-14"],
                    "analista": ["Marina"],
                    "prioridade": ["Alta"],
                }
            ),
            ["problema", "abertura", "analista", "prioridade"],
        ),
    ],
)
def test_file_reader_preserves_columns_for_three_layouts(
    tmp_path,
    filename,
    dataframe,
    expected_columns,
):
    file_path = tmp_path / filename

    if file_path.suffix == ".xlsx":
        _write_xlsx(file_path, dataframe)
    else:
        _write_csv(file_path, dataframe)

    result = FileReader.read(file_path)

    assert list(result.columns) == expected_columns


def test_file_reader_rejects_invalid_extension(tmp_path):
    file_path = tmp_path / "amostra.txt"
    file_path.write_text("texto")

    with pytest.raises(ValueError, match="Formato inválido"):
        FileReader.read(file_path)


def test_file_reader_rejects_large_files(tmp_path, monkeypatch):
    dataframe = pd.DataFrame(
        {
            "descricao": ["a", "b"],
        }
    )

    file_path = tmp_path / "grande.csv"
    _write_csv(file_path, dataframe)

    monkeypatch.setattr("app.ingestion.reader.MAX_ROWS", 1)

    with pytest.raises(ValueError, match="limite de 1 linhas"):
        FileReader.read(file_path)


def test_file_reader_allows_exact_row_limit(tmp_path, monkeypatch):
    dataframe = pd.DataFrame(
        {
            "descricao": ["a", "b"],
        }
    )

    file_path = tmp_path / "limite.csv"
    _write_csv(file_path, dataframe)

    monkeypatch.setattr("app.ingestion.reader.MAX_ROWS", 2)

    result = FileReader.read(file_path)

    assert len(result) == 2


def test_semantic_mapper_suggests_expected_fields():
    dataframe = pd.DataFrame(
        {
            "desc": ["Falha no acesso", "Tela congelou"],
            "dt": ["2026-05-14", "2026-05-15"],
            "analista": ["Marina", "Joao"],
        }
    )

    suggestions = SemanticMapper().suggest(dataframe)
    suggestion_map = {
        suggestion.source_column: suggestion.target_field for suggestion in suggestions
    }

    assert suggestion_map["desc"] == "descricao"
    assert suggestion_map["dt"] == "data"
    assert suggestion_map["analista"] == "responsavel"


def test_detect_columns_returns_suggestion_and_confidence():
    dataframe = pd.DataFrame(
        {
            "relato": [
                "Usuario nao consegue acessar a VPN corporativa",
                "Sistema apresenta erro ao abrir chamado",
            ],
            "data_abertura": [
                "2026-05-14",
                "2026-05-15",
            ],
            "owner": [
                "Marina",
                "Joao",
            ],
        }
    )

    detected = detect_columns(dataframe)

    assert detected["descricao"]["column"] == "relato"
    assert detected["descricao"]["confidence"] >= 0.7
    assert detected["data"]["column"] == "data_abertura"
    assert detected["data"]["confidence"] >= 0.7
    assert detected["responsavel"]["column"] == "owner"
    assert detected["responsavel"]["confidence"] >= 0.7


def test_mapping_validator_requires_descricao():
    with pytest.raises(ValueError, match="Campo obrigatório ausente: descricao"):
        MappingValidator.validate({"coluna_data": "data"})


def test_pipeline_executes_with_manual_mapping(tmp_path):
    dataframe = pd.DataFrame(
        {
            "descricao_ticket": ["Falha de rede"],
            "data_abertura": ["2026-05-14"],
            "responsavel_ticket": ["Carlos"],
        }
    )

    file_path = tmp_path / "tickets.csv"
    _write_csv(file_path, dataframe)

    result = IngestionPipeline().execute(
        file_path,
        mapping={
            "descricao_ticket": "descricao",
            "data_abertura": "data",
            "responsavel_ticket": "responsavel",
        },
    )

    assert list(result.columns) == ["descricao", "data", "responsavel"]


def test_api_upload_returns_structured_preview_response(tmp_path):
    client = TestClient(app, headers=AUTH_HEADERS)
    dataframe = pd.DataFrame(
        {
            "titulo": ["Falha no servidor"],
            "dt_ocorrencia": ["2026-05-14"],
            "tecnico_responsavel": ["Ana"],
        }
    )

    upload_name = "api_preview.csv"
    source_path = tmp_path / upload_name
    _write_csv(source_path, dataframe)

    with open(source_path, "rb") as file_handle:
        response = client.post(
            "/api/upload",
            files={"file": (upload_name, file_handle, "text/csv")},
        )

    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["file_id"].endswith(upload_name)
    assert payload["data"]["row_count"] == 1
    assert payload["data"]["columns"] == [
        "titulo",
        "dt_ocorrencia",
        "tecnico_responsavel",
    ]
    assert payload["data"]["suggested_mapping"]["descricao"] == "titulo"
    assert payload["data"]["preview_rows"][0]["titulo"] == "Falha no servidor"
    assert payload["data"]["limits"]["max_rows"] == 5000


def test_api_upload_returns_structured_error_for_invalid_extension():
    client = TestClient(app, headers=AUTH_HEADERS)

    response = client.post(
        "/api/upload",
        files={
            "file": (
                "chamados.txt",
                b"conteudo",
                "text/plain",
            )
        },
    )

    payload = response.json()

    assert response.status_code == 400
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_FILE_TYPE"
    assert "Formato inválido" in payload["error"]["message"]


def test_api_upload_rejects_files_over_row_limit(tmp_path, monkeypatch):
    client = TestClient(app, headers=AUTH_HEADERS)
    dataframe = pd.DataFrame(
        {
            "descricao": ["a", "b"],
        }
    )

    upload_name = "api_grande.csv"
    source_path = tmp_path / upload_name
    _write_csv(source_path, dataframe)

    monkeypatch.setattr("app.ingestion.reader.MAX_ROWS", 1)

    with open(source_path, "rb") as file_handle:
        response = client.post(
            "/api/upload",
            files={"file": (upload_name, file_handle, "text/csv")},
        )

    payload = response.json()

    assert response.status_code == 400
    assert payload["success"] is False
    assert payload["error"]["code"] == "ROW_LIMIT_EXCEEDED"
    assert "limite de 1 linhas" in payload["error"]["message"]


def test_api_process_returns_structured_records(tmp_path):
    client = TestClient(app, headers=AUTH_HEADERS)
    dataframe = pd.DataFrame(
        {
            "problema": ["Falha no acesso ao ERP"],
            "abertura": ["2026-05-14"],
            "analista": ["Ana"],
        }
    )

    upload_name = "api_process.csv"
    file_key = _stage_csv_in_s3(tmp_path, upload_name, dataframe)

    response = client.post(
        "/api/process",
        data={
            "file_id": file_key,
            "descricao": "problema",
            "data": "abertura",
            "responsavel": "analista",
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["row_count"] == 1
    assert payload["data"]["records"][0]["descricao"] == "Falha no acesso ao ERP"
    assert payload["data"]["mapping"] == {
        "problema": "descricao",
        "abertura": "data",
        "analista": "responsavel",
    }


def test_api_process_returns_structured_error_for_missing_required_mapping(tmp_path):
    client = TestClient(app, headers=AUTH_HEADERS)
    dataframe = pd.DataFrame(
        {
            "data": ["2026-05-14"],
        }
    )

    upload_name = "api_missing_mapping.csv"
    file_key = _stage_csv_in_s3(tmp_path, upload_name, dataframe)

    response = client.post(
        "/api/process",
        data={
            "file_id": file_key,
            "descricao": "",
            "data": "data",
            "responsavel": "",
        },
    )

    payload = response.json()

    assert response.status_code == 400
    assert payload["success"] is False
    assert payload["error"]["code"] == "MISSING_REQUIRED_FIELD"
    assert "Campo obrigatório ausente" in payload["error"]["message"]
