"""Stable, run-scoped redaction for model requests, retrieval and audit payloads."""

import re
from typing import Any, TypeVar, cast

T = TypeVar("T")
PATTERNS = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")),
    ("ID", re.compile(r"(?<!\d)\d{13}(?!\d)")),
    (
        "PHONE",
        re.compile(r"(?<!\w)(?:\+27[ -]?\d{2}(?:[ -]?\d){7}|0\d{2}[ -]?\d{3}[ -]?\d{4})(?!\w)"),
    ),
    ("ACCOUNT", re.compile(r"(?<!\d)\d{8,11}(?!\d)")),
]
PROTECTED = re.compile(r"\b(?:INV-?\d{6}|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})\b", re.I)


class Masker:
    """Retain token mappings only in memory for one investigation."""

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}
        self._counts: dict[str, int] = {}

    def text(self, value: str) -> str:
        """Mask sensitive patterns, preserving business invoice numbers and UUIDs."""
        protected: dict[str, str] = {}

        def protect(match: re.Match[str]) -> str:
            token = f"\x00{len(protected)}\x00"
            protected[token] = match.group()
            return token

        value = PROTECTED.sub(protect, value)
        for kind, pattern in PATTERNS:

            def replace(match: re.Match[str], category: str = kind) -> str:
                original = match.group()
                if original not in self._tokens:
                    self._counts[category] = self._counts.get(category, 0) + 1
                    self._tokens[original] = f"[{category}_{self._counts[category]}]"
                return self._tokens[original]

            value = pattern.sub(replace, value)
        for token, original in protected.items():
            value = value.replace(token, original)
        return value

    def clean(self, value: T) -> T:
        """Recursively mask text without changing numeric cents or container types."""
        return cast(T, self._walk(value, restore=False))

    def restore(self, value: T) -> T:
        """Restore a read-tool query locally; never send the mapping to a model."""
        return cast(T, self._walk(value, restore=True))

    def _walk(self, value: Any, *, restore: bool) -> Any:
        if isinstance(value, str):
            if not restore:
                return self.text(value)
            for original, token in self._tokens.items():
                value = value.replace(token, original)
            return value
        if isinstance(value, dict):
            return {key: self._walk(item, restore=restore) for key, item in value.items()}
        if isinstance(value, list):
            return [self._walk(item, restore=restore) for item in value]
        return value
