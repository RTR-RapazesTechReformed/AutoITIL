"""Client S3/MinIO para armazenamento do arquivo bruto de upload.

Convenção de key: uploads/<hash_conteudo>/<nome_original> — o hash evita
colisão entre arquivos homônimos de uploads diferentes (mesmo espírito de
arquivo.hash_conteudo em db/autoitil_schema_v4.sql).

Sem persistência no Postgres aqui — isso é responsabilidade de F1, quando
a tabela `arquivo` passar a ser gravada de fato.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

_S3_BUCKET = os.environ.get("S3_BUCKET", "autoitil-uploads")


def _client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL") or None,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


def build_key(content: bytes, filename: str) -> str:
    content_hash = hashlib.sha256(content).hexdigest()
    return f"uploads/{content_hash}/{filename}"


def upload_bytes(content: bytes, filename: str) -> str:
    """Sobe o conteúdo para o bucket e devolve a key S3."""
    key = build_key(content, filename)
    _client().put_object(Bucket=_S3_BUCKET, Key=key, Body=content)
    return key


def download_to_tempfile(key: str) -> Path:
    """Baixa o objeto do bucket para um arquivo temporário local e devolve
    o Path — o restante do pipeline de ingestão continua recebendo um Path
    local comum, sem precisar saber que o dado veio do S3."""
    suffix = Path(key).suffix
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    path = Path(tmp_path)
    try:
        _client().download_file(_S3_BUCKET, key, str(path))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def get_bucket_name() -> str:
    return _S3_BUCKET


def object_exists(key: str) -> bool:
    try:
        _client().head_object(Bucket=_S3_BUCKET, Key=key)
        return True
    except ClientError as error:
        status_code = error.response.get("Error", {}).get("Code")
        http_status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status_code == "404" or http_status == 404:
            return False
        raise
