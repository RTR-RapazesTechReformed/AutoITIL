"""CSVs "bagunçados": separador, encoding, cabeçalho deslocado, aliases.

Não depende de MinIO/banco: exercita só reader + mapper + pipeline.
"""

import pytest

from app.domain.errors import IngestionError
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.reader import FileReader

ROWS = [
    (
        "Servidor de arquivos fora do ar desde manhã, usuários sem acesso",
        "12/03/2024",
        "João",
    ),
    ("Não consigo acessar o sistema ERP, erro de login", "13/03/2024", "Maria"),
    ("Switch do 3º andar sem link, rede instável", "14/03/2024", "Pedro"),
]


def _q(value, sep):
    return f'"{value}"' if sep in value or '"' in value else value


def _csv(header, sep=",", rows=ROWS, prefix=""):
    lines = [sep.join(header)]
    lines += [sep.join(_q(v, sep) for v in row) for row in rows]
    return prefix + "\n".join(lines) + "\n"


def _write(tmp_path, name, text, encoding="utf-8"):
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return path


@pytest.mark.parametrize(
    ("sep", "encoding"),
    [
        (",", "utf-8"),
        (",", "utf-8-sig"),
        (";", "utf-8"),
        (";", "latin-1"),
        (",", "cp1252"),
        ("\t", "utf-8"),
        ("|", "utf-8"),
        (",", "utf-16"),
    ],
)
def test_reader_detects_separator_and_encoding(tmp_path, sep, encoding):
    path = _write(
        tmp_path,
        "a.csv",
        _csv(["descricao", "data", "responsavel"], sep=sep),
        encoding,
    )

    df = FileReader.read(path)

    assert list(df.columns) == ["descricao", "data", "responsavel"]
    assert len(df) == 3
    assert df["descricao"][0] == ROWS[0][0]
    assert df["responsavel"][0] == "João"


def test_reader_skips_title_lines_before_header(tmp_path):
    prefix = "Relatório de chamados - Março/2024\nGerado por: TI\n\n"
    path = _write(
        tmp_path,
        "b.csv",
        _csv(["descricao", "data", "responsavel"], prefix=prefix),
    )

    df = FileReader.read(path)

    assert list(df.columns) == ["descricao", "data", "responsavel"]
    assert len(df) == 3


def test_reader_skips_ragged_lines_and_blank_rows(tmp_path):
    text = (
        "descricao,data,responsavel,\n"
        "Servidor fora do ar há horas,12/03/2024,João,\n"
        "linha com campos demais,13/03/2024,Maria,x,y,z\n"
        ",,,\n"
        "Outro problema qualquer aqui,14/03/2024,Pedro,\n"
    )
    path = _write(tmp_path, "c.csv", text)

    df = FileReader.read(path)

    assert list(df.columns) == ["descricao", "data", "responsavel"]
    assert list(df["responsavel"]) == ["João", "Pedro"]


def test_reader_strips_header_whitespace(tmp_path):
    path = _write(
        tmp_path,
        "d.csv",
        _csv(["  Descrição do Chamado  ", "DATA_ABERTURA ", "Responsável"]),
    )

    df = FileReader.read(path)

    assert list(df.columns) == ["Descrição do Chamado", "DATA_ABERTURA", "Responsável"]


def test_reader_keeps_multiline_quoted_field(tmp_path):
    text = 'descricao,data\n"Linha um\nlinha dois do mesmo ticket",12/03/2024\n'
    path = _write(tmp_path, "e.csv", text)

    df = FileReader.read(path)

    assert len(df) == 1
    assert "linha dois" in df["descricao"][0]


def test_reader_still_rejects_empty_file(tmp_path):
    path = _write(tmp_path, "f.csv", "")

    with pytest.raises(IngestionError) as error:
        FileReader.read(path)

    assert error.value.code == "EMPTY_FILE"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (
            ["Resumo do incidente", "Abertura", "Técnico"],
            {
                "descricao": "Resumo do incidente",
                "data": "Abertura",
                "responsavel": "Técnico",
            },
        ),
        (
            ["number", "short_description", "opened_at", "assigned_to"],
            {
                "descricao": "short_description",
                "data": "opened_at",
                "responsavel": "assigned_to",
            },
        ),
        (
            ["id", "texto", "quando", "quem"],
            {"descricao": "texto"},
        ),
    ],
)
def test_mapper_recognizes_extra_aliases(tmp_path, header, expected):
    rows = [(i, *r) if header[0] in ("id", "number") else r for i, r in enumerate(ROWS)]
    path = _write(
        tmp_path,
        "g.csv",
        _csv([h for h in header], rows=[tuple(map(str, r)) for r in rows]),
    )

    _, suggestions = IngestionPipeline().preview(str(path))

    detected = {s.target_field: s.source_column for s in suggestions}
    for field, column in expected.items():
        assert detected.get(field) == column


def test_mapper_falls_back_to_longest_text_column_for_descricao(tmp_path):
    header = ["protocolo", "conteudo_livre", "criado"]
    rows = [(f"P{i}", r[0], r[1]) for i, r in enumerate(ROWS)]
    path = _write(tmp_path, "h.csv", _csv(header, rows=rows))

    out = IngestionPipeline().execute(str(path))

    assert list(out["descricao"]) == [r[0] for r in ROWS]


def test_pipeline_end_to_end_semicolon_latin1_messy_header(tmp_path):
    prefix = "Exportação do helpdesk\n\n"
    path = _write(
        tmp_path,
        "i.csv",
        _csv(
            ["Descrição do Chamado", "Data de Abertura", "Técnico"],
            sep=";",
            prefix=prefix,
        ),
        "latin-1",
    )

    out = IngestionPipeline().execute(str(path))

    assert list(out.columns) == ["descricao", "data", "responsavel"]
    assert len(out) == 3
    assert out["responsavel"][0] == "João"


def test_reader_ignores_separator_only_row_before_header(tmp_path):
    text = (
        "RELATÓRIO LEGADO\n"
        "Gerado em: 12/03/2024;Operador: ti;Filtro: TODOS\n"
        "\n"
        ";;;;\n"
        "Descrição;Data;Responsável;Status;\n"
        "Servidor fora do ar há horas;12/03/2024;João;Aberto;\n"
        ";;;;\n"
        "Erro de login no sistema ERP;13/03/2024;Maria;Aberto;\n"
    )
    path = _write(tmp_path, "j.csv", text, "cp1252")

    df = FileReader.read(path)

    assert list(df.columns) == ["Descrição", "Data", "Responsável", "Status"]
    assert len(df) == 2
