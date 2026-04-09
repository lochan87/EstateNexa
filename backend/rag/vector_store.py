import os
from pathlib import Path
from typing import Iterable

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

BASE_DIR = Path(__file__).resolve().parents[1]
VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", str(BASE_DIR / "data" / "chroma"))
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
PROPERTY_COLLECTION_NAME = os.getenv("PROPERTY_COLLECTION_NAME", "properties")


def _get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)


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
    store.persist()
