import os
import hashlib
import math
import re
from pathlib import Path
from typing import Iterable

from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document

try:
    from langchain_chroma import Chroma
except ImportError:  # pragma: no cover - fallback for environments without the newer package
    from langchain_community.vectorstores import Chroma

BASE_DIR = Path(__file__).resolve().parents[1]
VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", str(BASE_DIR / "data" / "chroma"))
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
PROPERTY_COLLECTION_NAME = os.getenv("PROPERTY_COLLECTION_NAME", "properties")
WORD_PATTERN = re.compile(r"[a-z0-9]+")


class LocalHashEmbeddings(Embeddings):
    """Deterministic offline embeddings based on feature hashing."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def _tokenize(self, text: str) -> list[str]:
        return WORD_PATTERN.findall((text or "").lower())

    def _vectorize(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = self._tokenize(text)

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], byteorder="big") % self.dimension
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectorize(text)


def _get_embeddings() -> Embeddings:
    if EMBEDDING_PROVIDER in {"huggingface", "hf", "sentence-transformers"}:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        except Exception:
            return LocalHashEmbeddings(dimension=EMBEDDING_DIMENSION)

    return LocalHashEmbeddings(dimension=EMBEDDING_DIMENSION)


def get_property_vector_store() -> Chroma:
    return Chroma(
        collection_name=PROPERTY_COLLECTION_NAME,
        embedding_function=_get_embeddings(),
        persist_directory=VECTOR_DB_DIR,
    )


def upsert_property_documents(documents: Iterable[Document]) -> None:
    docs = list(documents)
    if not docs:
        return

    store = get_property_vector_store()
    store.add_documents(docs)
