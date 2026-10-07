"""Local-only embedding implementations; hash is an honest nonsemantic baseline."""

import hashlib
import math
import re
from functools import lru_cache
from typing import Any, Protocol

from backend.app.config import get_settings


class Embedder(Protocol):
    """Compute a 384-dimensional vector without sending text to a third party."""

    def encode(self, text: str) -> list[float]:
        """Return one normalized vector."""
        ...


class HashEmbedder:
    """Deterministic signed feature hashing for tests and offline demonstrations."""

    def encode(self, text: str) -> list[float]:
        """Hash words and character trigrams into a unit vector."""
        vector = [0.0] * 384
        words = re.findall(r"[a-z0-9]+", text.lower())
        features = words + [word[i : i + 3] for word in words for i in range(max(0, len(word) - 2))]
        for feature in features:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            vector[int.from_bytes(digest[:4]) % 384] += 1 if digest[4] % 2 else -1
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1
        return [value / magnitude for value in vector]


class LocalEmbedder:
    """MiniLM runs on this machine; the checkpoint must be cached before offline use."""

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model: Any = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2", local_files_only=True
        )

    def encode(self, text: str) -> list[float]:
        """Encode text locally, rejecting an incompatible embedding dimension."""
        values = [float(x) for x in self.model.encode(text, normalize_embeddings=True).tolist()]
        if len(values) != 384:
            raise ValueError("embedding model must produce 384 dimensions")
        return values


@lru_cache
def get_embedder() -> Embedder:
    """Construct the explicitly configured local embedder."""
    return HashEmbedder() if get_settings().embedder == "hash" else LocalEmbedder()
