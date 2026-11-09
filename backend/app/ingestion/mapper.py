from difflib import SequenceMatcher

import pandas as pd
from dateutil.parser import parse

from app.domain.constants import TARGET_FIELDS
from app.domain.models import MappingSuggestion
from app.utils.text_normalizer import (
    TextNormalizer,
)


class SemanticMapper:
    def __init__(self):
        self.normalizer = TextNormalizer()

    def _similarity(self, first_value, second_value):
        return SequenceMatcher(
            None,
            first_value,
            second_value,
        ).ratio()

    def _alias_score(self, normalized_column, normalized_alias):
        if normalized_column == normalized_alias:
            return 1.0

        if normalized_alias in normalized_column:
            return 0.92

        if normalized_column in normalized_alias:
            return 0.8

        return (
            self._similarity(
                normalized_column,
                normalized_alias,
            )
            * 0.75
        )

    def _looks_like_date(self, value):
        if pd.isna(value):
            return False

        if hasattr(value, "date"):
            return True

        value_as_text = str(value).strip()

        if not value_as_text:
            return False

        has_date_marker = any(marker in value_as_text for marker in ["/", "-", ":"])

        if not has_date_marker:
            return False

        try:
            parse(value_as_text)
            return True

        except Exception:
            return False

    def _sample_score(self, sample, field, metadata):
        values = [value for value in sample if not pd.isna(value)]

        if not values:
            return 0.0

        if field == "data":
            date_count = sum(1 for value in values if self._looks_like_date(value))
            return date_count / len(values)

        normalized_aliases = [
            self.normalizer.normalize(alias) for alias in metadata["aliases"]
        ]

        keyword_hits = 0

        for value in values:
            normalized_value = self.normalizer.normalize(str(value))

            if not normalized_value:
                continue

            if any(alias in normalized_value for alias in normalized_aliases):
                keyword_hits += 1

        if field == "descricao":
            text_values = [
                str(value) for value in values if len(str(value).strip()) >= 12
            ]
            return min(
                1.0,
                (len(text_values) / len(values)) * 0.7
                + (keyword_hits / len(values)) * 0.3,
            )

        return keyword_hits / len(values)

    def _field_score(self, column, sample, field, metadata):
        normalized_column = self.normalizer.normalize(column)
        alias_scores = []

        for alias in metadata["aliases"]:
            normalized_alias = self.normalizer.normalize(alias)

            alias_scores.append(
                self._alias_score(
                    normalized_column,
                    normalized_alias,
                )
            )

        header_score = max(alias_scores, default=0.0)
        sample_score = self._sample_score(
            sample,
            field,
            metadata,
        )

        return min(
            1.0,
            header_score * 0.8 + sample_score * 0.2,
        )

    def detect_columns(self, dataframe):
        candidates = []

        for column in dataframe.columns:
            sample = dataframe[column].head(5)

            for field, metadata in TARGET_FIELDS.items():
                score = self._field_score(
                    column,
                    sample,
                    field,
                    metadata,
                )

                candidates.append(
                    (
                        score,
                        field,
                        column,
                    )
                )

        detected = {
            field: {
                "column": None,
                "confidence": 0.0,
            }
            for field in TARGET_FIELDS
        }
        used_columns = set()
        used_fields = set()

        for score, field, column in sorted(
            candidates,
            key=lambda candidate: candidate[0],
            reverse=True,
        ):
            if score < 0.45:
                continue

            if field in used_fields or column in used_columns:
                continue

            detected[field] = {
                "column": column,
                "confidence": round(score, 2),
            }
            used_fields.add(field)
            used_columns.add(column)

        return detected

    def suggest(self, dataframe):
        suggestions = []
        detected_columns = self.detect_columns(dataframe)

        for field, suggestion in detected_columns.items():
            if suggestion["column"]:
                suggestions.append(
                    MappingSuggestion(
                        source_column=suggestion["column"],
                        target_field=field,
                        confidence=suggestion["confidence"],
                    )
                )

        return suggestions


def detect_columns(dataframe):
    return SemanticMapper().detect_columns(dataframe)
