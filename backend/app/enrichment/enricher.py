"""
enricher.py — reescreve a descrição de um ticket de forma mais legível
usando um LLM pequeno (F2-4), num formato estruturado: objetivo do ticket,
requisições pra completá-lo (lista de itens), e recomendação de cargo do
responsável.

Responsabilidade: dado o texto bruto de um ticket (normalmente cheio de
abreviações, erros de digitação e jargão informal, como digitado por quem
abriu o chamado), gerar uma análise estruturada em português, preservando
o sentido original.

Design (mesmo espírito de app.classification.bert_classifier.BertClassifier):
- Carregamento lazy: o modelo só vai para a memória na primeira chamada de
  enrich(), evitando custo na inicialização da aplicação.
- Graceful degradation: se transformers/torch não conseguirem carregar o
  modelo por qualquer motivo (sem rede, sem HF_TOKEN pra um modelo gated,
  timeout, OOM), is_available() reflete isso e enrich() retorna None — o
  chamador decide o que fazer (nesta app: a rota devolve 503, ver POST
  /api/tickets/{id}/enrich).
- Saída estruturada via marcadores de texto, não JSON direto do modelo:
  um modelo pequeno tem mais chance de produzir JSON malformado do que
  texto com marcadores simples por linha — o parsing (_parse_structured_
  output) é tolerante campo a campo, não tudo-ou-nada. O campo
  REQUISIÇÕES continua sendo uma única linha (mesmo formato confiável),
  mas com itens separados por ";" — o parser divide essa linha numa
  lista, em vez de pedir ao modelo múltiplas linhas numeradas (mais
  arriscado para um modelo desse tamanho acertar em sequência).
- Deliberadamente NÃO é chamado em lote durante a ingestão: rodar geração de
  texto por LLM para até MAX_ROWS (5000) linhas de uma vez, em CPU, é
  proibitivamente lento para um MVP. É chamado sob demanda, um ticket por
  vez (ver POST /api/tickets/{id}/enrich em app/api/routes.py), e o
  resultado fica em cache em ticket.descricao_enriquecida (serializado como
  JSON — ver app.tickets.queries.save_enriched_description).
- Geração via model.generate() padrão do transformers (decodificação
  gulosa, do_sample=False) — versões anteriores deste módulo usavam um
  loop manual de decodificação pra contornar um segfault documentado de
  generate() com Qwen2ForCausalLM nas versões antigas pinadas de
  transformers/torch. Esse segfault não se reproduz mais na versão atual
  de transformers, e o loop manual não é compatível com o cache de
  tamanho fixo do Gemma3 — por isso a API padrão é usada diretamente.
"""

from __future__ import annotations

import logging
import re
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)

MAX_NEW_TOKENS = 150  # três frases curtas + labels (era 60 pra frase única)

SYSTEM_PROMPT = (
    "Analise a descrição de um chamado de TI em português do Brasil e "
    "responda em exatamente três linhas, cada uma com um marcador no "
    "início, sem nada antes ou depois delas. Mantenha os mesmos fatos do "
    "texto original (sistema, erro, prazo) — o chamado ainda está aberto "
    "e sem solução, nunca diga que foi resolvido nem sugira causa ou "
    "solução.\n\n"
    "Formato exato:\n"
    "OBJETIVO: <o que o chamado está pedindo, uma frase curta>\n"
    "REQUISIÇÕES: <itens do que falta pra resolver o chamado, separados "
    "por ponto e vírgula (;)>\n"
    "CARGO: <cargo ou área que deveria assumir o chamado, uma frase curta>\n\n"
    "Exemplo:\n"
    "Entrada: impressora 3o andar nao imprime, da erro de driver\n"
    "OBJETIVO: Resolver a impressora do 3º andar que não imprime e "
    "apresenta erro de driver.\n"
    "REQUISIÇÕES: Reinstalar ou atualizar o driver da impressora; Verificar "
    "a fila de impressão.\n"
    "CARGO: Suporte técnico de TI."
)

# Reconhece "OBJETIVO:", "REQUISIÇÕES:"/"REQUISICOES:" (\w é Unicode-aware
# em Python 3, cobre a cedilha/til sem precisar listar as duas grafias) e
# "CARGO:", em qualquer posição de linha, com ou sem espaço antes do valor.
_FIELD_PATTERN = re.compile(
    r"^(OBJETIVO|REQUISI\w*|CARGO):\s*(.+)$", re.IGNORECASE | re.MULTILINE
)

_PLACEHOLDER = "Não informado pelo modelo."


def _label_to_key(label: str) -> str | None:
    normalized = label.strip().lower()
    if normalized == "objetivo":
        return "objetivo"
    if normalized.startswith("requisi"):
        return "requisicoes"
    if normalized == "cargo":
        return "cargo_recomendado"
    return None


def _split_requisicoes(raw: str) -> list[str]:
    """Divide a linha bruta de REQUISIÇÕES em itens, por ';'. Remove
    espaços em volta de cada item e descarta itens vazios (ex.: ';;' ou
    ';' sobrando no fim da linha). Remove período final se presente."""
    text = raw.rstrip(".")
    itens = [item.strip() for item in text.split(";")]
    return [item for item in itens if item]


def _parse_structured_output(texto: str) -> dict[str, str | list[str]] | None:
    """Extrai objetivo/requisições/cargo do texto gerado pelo modelo.

    Tolerante: se algum campo não bater no formato esperado, vira um
    placeholder em vez de descartar os campos que saíram certos. Só
    retorna None se NENHUM marcador for reconhecido (falha total — mesmo
    contrato que o resto do enricher usa pra "não deu pra enriquecer")."""
    fields: dict[str, str] = {}
    for label, value in _FIELD_PATTERN.findall(texto):
        key = _label_to_key(label)
        if key and key not in fields:
            fields[key] = value.strip()

    if not fields:
        return None

    requisicoes_raw = fields.get("requisicoes")
    requisicoes = _split_requisicoes(requisicoes_raw) if requisicoes_raw else []
    if not requisicoes:
        requisicoes = [_PLACEHOLDER]

    return {
        "objetivo": fields.get("objetivo", _PLACEHOLDER),
        "requisicoes": requisicoes,
        "cargo_recomendado": fields.get("cargo_recomendado", _PLACEHOLDER),
    }


class DescriptionEnricher:
    """
    DescriptionEnricher — analisa a descrição de tickets via LLM pequeno,
    devolvendo objetivo / requisições (lista) / cargo recomendado.

    Carregamento lazy, mesmo contrato de graceful degradation do
    BertClassifier: is_available() indica se o modelo pôde ser carregado;
    enrich() retorna None (nunca lança) se o modelo não estiver
    disponível ou a geração falhar.

    Exemplo:
        enricher = DescriptionEnricher(model_name="google/gemma-3-1b-it")
        if enricher.is_available():
            resultado = enricher.enrich("vpn nao conecta desde ontem")
            # → {"objetivo": "...", "requisicoes": ["...", "..."], "cargo_recomendado": "..."}
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._tokenizer = None
        self._model = None
        self._load_failed = False
        # Métricas da última chamada BEM-SUCEDIDA de enrich() — None até a
        # primeira chamada bem-sucedida; não são resetadas por chamadas que
        # falham (ver enrich()). Lidas pelo chamador (app.api.routes) logo
        # após enrich() devolver um resultado não-None, pra persistir via
        # app.domain.enrichment_metrics.record_enrichment_metric.
        self.last_call_duration_ms: float | None = None
        self.last_call_tokens_entrada: int | None = None
        self.last_call_tokens_saida: int | None = None

    def is_available(self) -> bool:
        """Tenta carregar o modelo (se ainda não carregado) e reporta se
        está pronto para uso. Chamado antes de enrich() pelas rotas para
        decidir se vale a pena tentar, mas enrich() também é seguro de
        chamar diretamente (faz o mesmo carregamento lazy)."""
        self._load()
        return self._model is not None

    def _load(self) -> None:
        if self._model is not None or self._load_failed:
            return
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_name, torch_dtype=torch.float32
            )
            self._model.eval()
        except Exception:
            # Sem rede, sem HF_TOKEN pra modelo gated, modelo removido do
            # Hub, OOM, etc. — degrada graciosamente em vez de derrubar a
            # rota que chamou.
            logger.warning("enricher_load_failed", exc_info=True)
            self._load_failed = True
            self._tokenizer = None
            self._model = None

    def enrich(self, descricao_original: str) -> dict[str, str | list[str]] | None:
        """
        Analisa `descricao_original` e devolve objetivo/requisições/cargo.

        Args:
            descricao_original: texto bruto do ticket (ex.: registro.descricao_original).

        Returns:
            dict com chaves 'objetivo' (str), 'requisicoes' (list[str]),
            'cargo_recomendado' (str), ou None se o modelo não estiver
            disponível, a geração falhar, ou nenhum campo reconhecível
            sair na saída.
        """
        self._load()
        if self._model is None or self._tokenizer is None:
            return None

        try:
            start = time.perf_counter()
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": descricao_original},
            ]
            prompt = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            encoded = self._tokenizer(prompt, return_tensors="pt")
            with torch.no_grad():
                generated = self._model.generate(
                    **encoded,
                    max_new_tokens=MAX_NEW_TOKENS,
                    do_sample=False,
                )
            duration_ms = (time.perf_counter() - start) * 1000
            tokens_entrada = encoded["input_ids"].shape[1]
            tokens_saida = generated[0].shape[0] - tokens_entrada

            texto = self._tokenizer.decode(
                generated[0][tokens_entrada:],
                skip_special_tokens=True,
            ).strip()
            resultado = _parse_structured_output(texto) if texto else None
            if resultado is not None:
                self.last_call_duration_ms = duration_ms
                self.last_call_tokens_entrada = tokens_entrada
                self.last_call_tokens_saida = tokens_saida
            return resultado
        except Exception:
            logger.warning("enrich_generation_failed", exc_info=True)
            return None
