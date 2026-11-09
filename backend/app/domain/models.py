from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    __table_args__ = {"schema": "autoitil"}


class Prioridade(Base):
    __tablename__ = "prioridade"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(2))
    descricao: Mapped[str] = mapped_column(String(60))
    ordem: Mapped[int] = mapped_column(SmallInteger)


class TipoItil(Base):
    __tablename__ = "tipo_itil"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(String(30))
    prioridade_padrao_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("autoitil.prioridade.id")
    )


class StatusTicket(Base):
    __tablename__ = "status_ticket"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30))
    descricao: Mapped[str] = mapped_column(String(60))
    ordem: Mapped[int] = mapped_column(SmallInteger)


class AreaResponsavel(Base):
    __tablename__ = "area_responsavel"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(String(30))


class LimiarConfianca(Base):
    """Calibração de limiar de confiança (F2-1, ainda não implementado) —
    mapeado apenas para que `Ticket.limiar_confianca_id` consiga resolver a
    FK; a coluna sempre fica NULL nesta fase (F1-1)."""

    __tablename__ = "limiar_confianca"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    valor: Mapped[float] = mapped_column(Numeric(4, 3))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Modelo(Base):
    __tablename__ = "modelo"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    arquitetura: Mapped[str] = mapped_column(String(20))
    nivel: Mapped[int] = mapped_column(SmallInteger)
    ativo: Mapped[bool] = mapped_column(Boolean)


class Arquivo(Base):
    __tablename__ = "arquivo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome_original: Mapped[str] = mapped_column(String(255))
    extensao: Mapped[str] = mapped_column(String(10))
    hash_conteudo: Mapped[str] = mapped_column(CHAR(64))
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    total_linhas: Mapped[int] = mapped_column(Integer)
    storage_backend: Mapped[str] = mapped_column(String(10), default="s3")
    storage_uri: Mapped[str] = mapped_column(String(500))
    data_upload: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HistoricoUpload(Base):
    __tablename__ = "historico_upload"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome_original: Mapped[str] = mapped_column(String(255))
    extensao: Mapped[str] = mapped_column(String(10))
    hash_conteudo: Mapped[str] = mapped_column(CHAR(64))
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    storage_uri: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="recebido")
    total_linhas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mensagem_erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MetricaSistema(Base):
    __tablename__ = "metrica_sistema"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cpu_percent: Mapped[float] = mapped_column(Numeric(7, 3))
    memory_rss_mb: Mapped[float] = mapped_column(Numeric(12, 3))
    memory_percent: Mapped[float] = mapped_column(Numeric(7, 3))
    uptime_seconds: Mapped[float] = mapped_column(Numeric(14, 3))
    coletado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MetricaEnriquecimento(Base):
    __tablename__ = "metrica_enriquecimento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duracao_ms: Mapped[float] = mapped_column(Numeric(12, 3))
    tokens_entrada: Mapped[int] = mapped_column(Integer)
    tokens_saida: Mapped[int] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MetricaClassificacao(Base):
    __tablename__ = "metrica_classificacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nivel: Mapped[int] = mapped_column(SmallInteger)
    arquitetura: Mapped[str] = mapped_column(String(10))
    duracao_ms: Mapped[float] = mapped_column(Numeric(12, 3))
    tokens_entrada: Mapped[int] = mapped_column(Integer)
    itens: Mapped[int] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Registro(Base):
    __tablename__ = "registro"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    arquivo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("autoitil.arquivo.id")
    )
    linha_origem: Mapped[int] = mapped_column(Integer)
    descricao_original: Mapped[str] = mapped_column(Text)
    data_registro: Mapped[date | None] = mapped_column(nullable=True)
    responsavel: Mapped[str | None] = mapped_column(String(120), nullable=True)


class TextoProcessado(Base):
    __tablename__ = "texto_processado"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    registro_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("autoitil.registro.id")
    )
    descricao_limpa: Mapped[str] = mapped_column(Text)


class Classificacao(Base):
    __tablename__ = "classificacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    texto_processado_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("autoitil.texto_processado.id")
    )
    tipo_itil_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("autoitil.tipo_itil.id")
    )
    area_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("autoitil.area_responsavel.id"), nullable=True
    )
    modelo_n1_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("autoitil.modelo.id")
    )
    modelo_n2_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("autoitil.modelo.id"), nullable=True
    )
    confianca_n1: Mapped[float] = mapped_column(Numeric(6, 5))
    confianca_n2: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True)


class Ticket(Base):
    __tablename__ = "ticket"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    classificacao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("autoitil.classificacao.id")
    )
    codigo: Mapped[str] = mapped_column(String(12))
    titulo_sugerido: Mapped[str] = mapped_column(String(120))
    prioridade_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("autoitil.prioridade.id")
    )
    status_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("autoitil.status_ticket.id")
    )
    limiar_confianca_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("autoitil.limiar_confianca.id"), nullable=True
    )
    descricao_enriquecida: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_geracao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TicketStatusHistorico(Base):
    __tablename__ = "ticket_status_historico"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("autoitil.ticket.id"))
    status_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("autoitil.status_ticket.id")
    )
    data_transicao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    observacao: Mapped[str | None] = mapped_column(String(255), nullable=True)


class RevisaoClassificacao(Base):
    __tablename__ = "revisao_classificacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("autoitil.ticket.id"), unique=True
    )
    tipo_itil_original_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("autoitil.tipo_itil.id"), nullable=True
    )
    tipo_itil_revisado_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("autoitil.tipo_itil.id"), nullable=True
    )
    tipo_itil_revisado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    area_original_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("autoitil.area_responsavel.id"), nullable=True
    )
    area_revisado_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("autoitil.area_responsavel.id"), nullable=True
    )
    area_revisado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FeedbackEnriquecimento(Base):
    __tablename__ = "feedback_enriquecimento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("autoitil.ticket.id"), unique=True
    )
    valor: Mapped[str] = mapped_column(String(4))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Organizacao(Base):
    __tablename__ = "organizacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CustoEvento(Base):
    __tablename__ = "custo_evento"

    tipo_evento: Mapped[str] = mapped_column(String(30), primary_key=True)
    custo_unidade_centavos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custo_mil_tokens_entrada_centavos: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    custo_mil_tokens_saida_centavos: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RelatorioCusto(Base):
    __tablename__ = "relatorio_custo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organizacao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("autoitil.organizacao.id")
    )
    periodo_inicio: Mapped[date] = mapped_column(Date)
    periodo_fim: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="aberta")
    total_centavos: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fechado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (  # type: ignore[assignment]
        UniqueConstraint(
            "organizacao_id", "periodo_inicio", "periodo_fim", name="uq_relatorio_custo_periodo_org"
        ),
        {"schema": "autoitil"},
    )


class RelatorioCustoItem(Base):
    __tablename__ = "relatorio_custo_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    relatorio_custo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("autoitil.relatorio_custo.id")
    )
    tipo_evento: Mapped[str] = mapped_column(String(30))
    quantidade_total: Mapped[int] = mapped_column(Integer)
    custo_total_centavos: Mapped[int] = mapped_column(Integer)


class EventoCusto(Base):
    __tablename__ = "evento_custo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organizacao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("autoitil.organizacao.id")
    )
    tipo_evento: Mapped[str] = mapped_column(String(30))
    quantidade: Mapped[int] = mapped_column(Integer)
    tokens_entrada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_saida: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referencia_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    custo_unitario_centavos: Mapped[int] = mapped_column(Integer)
    custo_centavos: Mapped[int] = mapped_column(Integer)
    relatorio_custo_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("autoitil.relatorio_custo.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organizacao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("autoitil.organizacao.id")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


@dataclass
class MappingSuggestion:
    source_column: str
    target_field: str
    confidence: float
