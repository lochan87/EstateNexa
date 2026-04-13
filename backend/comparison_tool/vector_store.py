from typing import Iterable

import chromadb
from langchain_core.documents import Document

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings

try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

try:
    from .config import get_settings
except ImportError:
    from config import get_settings


def get_embeddings() -> HuggingFaceEmbeddings:
    settings = get_settings()
    return HuggingFaceEmbeddings(model_name=settings.embedding_model_name)


def get_vector_store() -> Chroma:
    settings = get_settings()
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=settings.collection_name,
        persist_directory=str(settings.chroma_dir),
        embedding_function=get_embeddings(),
    )


def upsert_documents(documents: Iterable[Document], ids: list[str]) -> int:
    docs = list(documents)
    if not docs:
        return 0

    store = get_vector_store()
    store.add_documents(docs, ids=ids)
    store.persist()
    return len(docs)


def collection_document_count() -> int:
    settings = get_settings()
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    try:
        collection = client.get_collection(name=settings.collection_name)
    except Exception:
        return 0
    return int(collection.count())
