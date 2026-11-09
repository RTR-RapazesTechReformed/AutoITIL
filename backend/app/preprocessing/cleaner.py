"""
cleaner.py — pré-processamento textual para pipeline TF-IDF.

Responsabilidade: transformar texto bruto de tickets em uma versão normalizada,
reduzida e consistente para vetorização.

Design:
- Classe TextCleaner segue padrão stateless do projeto
  (FileReader, SemanticMapper, DataTransformer).
- Normalização de acentos via unicodedata (NFKD).
- Aplicação de regras de preservação de termos técnicos definidos em arquivo externo
  (ex: VPN, SLA, K8S, CI/CD), garantindo consistência semântica.
- Remoção de ruídos comuns (e-mails, URLs, chamadas, horários), pontuação e stop-words.
- Normalização de termos compostos e com separadores (ex: "ci/cd" → "ci cd").

Observação:
- O pipeline prioriza interpretabilidade e separação de tokens para uso com TF-IDF,
  evitando colapsos semânticos agressivos.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import nltk
from nltk.corpus import stopwords as _nltk_stopwords


def _load_stopwords() -> frozenset[str]:
    for resource in ("stopwords",):
        try:
            nltk.data.find(f"corpora/{resource}")
        except LookupError:
            nltk.download(resource, quiet=True)

    return frozenset(_nltk_stopwords.words("portuguese"))


_STOPWORDS_PT = _load_stopwords()

_PATTERN_EMAIL = re.compile(r"\S+@\S+\.\S+")
_PATTERN_URL = re.compile(r"https?://\S+|www\.\S+")
_PATTERN_CHAMADO = re.compile(r"#\d+")
_PATTERN_HORA = re.compile(r"[a-z]*\d{1,2}h\d{0,2}")
_PATTERN_NONALPHA = re.compile(r"[^a-z0-9\s]")

_DEFAULT_PROTECTED_PATH = Path("data/config/protected_terms.txt")


@lru_cache(maxsize=1)
def _load_protected_terms(path: str) -> frozenset[str]:
    p = Path(path)
    if not p.exists():
        return frozenset()
    terms: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.add(line.lower())
    return frozenset(terms)


def _remove_accents(text: str) -> str:
    """Remove acentos via NFD, mesmo método usado pelo TextNormalizer do projeto."""
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


class TextCleaner:
    """
    TextCleaner — pré-processamento de tickets para modelos de classificação baseados em TF-IDF.

    Este componente transforma textos de incidentes e requisições de TI em uma representação
    normalizada e consistente, removendo ruídos comuns (e-mails, URLs, caracteres especiais,
    stop-words) e preservando termos técnicos relevantes ao domínio (ex: VPN, SLA, CI/CD).

    O objetivo é reduzir variabilidade textual mantendo a estrutura semântica essencial,
    facilitando a vetorização por modelos clássicos como TF-IDF.

    Exemplo:
        cleaner = TextCleaner()
        cleaner.clean("VPN do escritório caiu desde as14h30.")
        # → "vpn escritorio caiu"

        df_clean = cleaner.clean_dataframe(df, col="descricao")
        # adiciona coluna 'descricao_limpa' ao DataFrame
    """

    def __init__(
        self,
        protected_terms_path: str | Path = _DEFAULT_PROTECTED_PATH,
    ):
        self._protected_path = str(protected_terms_path)
        self._protected_map = {}
        self._protected_terms = _load_protected_terms(self._protected_path)

        self._protected_patterns = [
            (
                re.escape(term.lower()),
                self._normalize_protected(term),
            )
            for term in sorted(self._protected_terms, key=len, reverse=True)
        ]

    def _normalize_protected(self, term: str) -> str:
        return re.sub(r"[\s/]+", "", term.lower())

    def clean(self, text: str) -> str:
        """
        Normaliza texto de tickets de suporte para uso em modelos de classificação baseados em TF-IDF.

        O objetivo é reduzir ruído textual mantendo termos técnicos relevantes do domínio de TI,
        garantindo consistência na vetorização de incidentes e requisições.

        Pipeline:
            1. Conversão para lowercase
            2. Preservação de termos técnicos (ex: VPN, SLA, CI/CD)
            3. Remoção de ruídos estruturais (e-mails, URLs, chamados, horários)
            4. Normalização de acentos (NFKD)
            5. Remoção de pontuação e caracteres especiais
            6. Remoção de stop-words PT-BR e tokens de baixa relevância

        Args:
            text: Texto bruto da descrição do ticket.

        Returns:
            Texto limpo e normalizado pronto para vetorização.
        """
        if not isinstance(text, str) or not text.strip():
            return ""

        # 1. converter para lowercase
        t = text.lower()

        # 2. proteger termos
        for pattern, normalized in self._protected_patterns:
            t = re.sub(pattern, normalized, t)

        # 3. remover ruídos estruturais
        t = _PATTERN_EMAIL.sub(" ", t)
        t = _PATTERN_URL.sub(" ", t)
        t = _PATTERN_CHAMADO.sub(" ", t)
        t = _PATTERN_HORA.sub(" ", t)

        # 4. normalizar acentos
        t = _remove_accents(t)

        # 5. remover pontuação / caracteres especiais
        t = _PATTERN_NONALPHA.sub(" ", t)

        # 6. filtrar stop-words e tokens curtos
        tokens = [
            tok
            for tok in t.split()
            if tok and (tok not in _STOPWORDS_PT and len(tok) > 1)
        ]

        return " ".join(tokens)

    def clean_dataframe(
        self,
        dataframe,
        col: str = "descricao",
        output_col: str = "descricao_limpa",
    ):
        """
        Aplica limpeza textual à coluna especificada do DataFrame utilizando o método clean(),
        retornando uma versão pronta para uso em modelos de classificação baseados em TF-IDF.

        Não modifica o DataFrame original (retorna uma cópia).

        Args:
            dataframe: DataFrame contendo a coluna de texto de tickets.
            col: Nome da coluna de entrada (padrão: "descricao").
            output_col: Nome da coluna de saída com texto limpo.

        Returns:
            DataFrame com a coluna `output_col` adicionada.
        """

        result = dataframe.copy()
        result[output_col] = result[col].fillna("").astype(str).apply(self.clean)
        return result
