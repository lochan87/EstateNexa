"""Role-aware document summarization orchestration."""

from __future__ import annotations

from pathlib import Path
import re

from .pdf_reader import read_pdf
from .summarizer import generate_summary

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS_DIR = PROJECT_ROOT / "Documents"
MAX_INPUT_CHARS = 18000
PER_DOCUMENT_CHAR_LIMIT = 4500
RAG_TOP_K = 5
RAG_CONTEXT_CHAR_LIMIT = 9000


def _categorize_document(file_name: str) -> str:
    normalized_name = file_name.lower()

    if "legal" in normalized_name or "compliance" in normalized_name:
        return "legal"

    if "financial" in normalized_name or "investment" in normalized_name:
        return "financial"

    if "property" in normalized_name or "listing" in normalized_name:
        return "property"

    if "market" in normalized_name or "location" in normalized_name:
        return "market"

    return "market"


def _discover_documents() -> list[dict[str, str]]:
    if not DOCUMENTS_DIR.is_dir():
        return []

    discovered = []
    for pdf_path in sorted(DOCUMENTS_DIR.glob("*.pdf")):
        discovered.append(
            {
                "category": _categorize_document(pdf_path.name),
                "file_path": f"Documents/{pdf_path.name}",
            }
        )

    return discovered


def _role_priority(role: str) -> list[str]:
    if role == "buyer":
        return ["property", "market"]

    if role == "agent":
        return ["financial", "property", "market"]

    return ["legal", "financial", "property", "market"]


def _extract_query_keywords(query: str) -> list[str]:
    """Extract lowercase keywords from query."""
    if not query:
        return []

    words = re.findall(r"\b\w+\b", query.lower())
    stop_words = {"the", "a", "an", "and", "or", "is", "are", "for", "in", "on", "at", "to", "of", "by"}
    return [w for w in words if w not in stop_words and len(w) > 2]


def _calculate_relevance(text: str, keywords: list[str]) -> int:
    """Calculate relevance score based on keyword matches."""
    if not keywords:
        return 1

    text_lower = text.lower()
    score = 0
    for keyword in keywords:
        score += len(re.findall(rf"\b{re.escape(keyword)}\b", text_lower))

    return max(1, score)


def _extract_relevant_sections(text: str, keywords: list[str], max_chars: int = 2000) -> str:
    """Extract query-relevant sections from text."""
    if not keywords or not text:
        return text[:max_chars]

    sentences = re.split(r"[.!?]\s+", text)
    scored_sentences = []
    for sent in sentences:
        if sent.strip():
            score = _calculate_relevance(sent, keywords)
            if score > 0:
                scored_sentences.append((score, sent.strip()))

    if not scored_sentences:
        return text[:max_chars]

    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    selected = [s[1] for s in scored_sentences[:10]]
    result = ". ".join(selected)
    return result[:max_chars]


def _fetch_rag_context(role: str, query: str) -> str:
    """Fetch semantic context from the vector store for the given query."""
    normalized_query = (query or "").strip()
    if not normalized_query:
        return ""

    try:
        from rag.models import PropertyFilters
        from rag.retrieval import property_retrieval_tool
    except Exception:
        return ""

    try:
        results = property_retrieval_tool(
            query=normalized_query,
            filters=PropertyFilters(),
            user_role=role,
            top_k=RAG_TOP_K,
        )
    except Exception:
        return ""

    if not results:
        return ""

    chunks = []
    for index, item in enumerate(results, start=1):
        highlights = item.get("highlights") or []
        highlights_text = "; ".join(str(point) for point in highlights[:3])
        chunks.append(
            (
                f"Result {index} | ID: {item.get('property_id', '')} | "
                f"Location: {item.get('location', '')} | "
                f"Type: {item.get('property_type', '')} | "
                f"Bedrooms: {item.get('bedrooms', '')}\n"
                f"Highlights: {highlights_text}\n"
                f"Snippet: {(item.get('summary') or '').strip()}"
            )
        )

    return "\n\n".join(chunks)[:RAG_CONTEXT_CHAR_LIMIT]

ROLE_CATEGORIES = {
    "buyer": {"market", "property"},
    "agent": {"market", "property", "financial"},
    "admin": {"market", "property", "financial", "legal"},
}


def summarize_documents(role: str, query: str = "") -> str:
    """Read role-allowed documents and return a consolidated summary.
    
    If query is provided, fetch only relevant sections.
    """

    role_key = (role or "").strip().lower()
    normalized_role = role_key if role_key in ROLE_CATEGORIES else "buyer"
    rag_context = _fetch_rag_context(normalized_role, query)
    allowed_categories = ROLE_CATEGORIES[normalized_role]
    documents = _discover_documents()
    if not documents and not rag_context:
        return ""

    selected_docs = [doc for doc in documents if doc["category"] in allowed_categories]
    priority_order = {category: index for index, category in enumerate(_role_priority(normalized_role))}
    selected_docs.sort(key=lambda doc: priority_order.get(doc["category"], 99))

    keywords = _extract_query_keywords(query)
    extracted_parts = []
    for doc in selected_docs:
        path = doc["file_path"]
        text = read_pdf(path)
        if text:
            if keywords:
                relevant_text = _extract_relevant_sections(text, keywords, PER_DOCUMENT_CHAR_LIMIT)
            else:
                relevant_text = text[:PER_DOCUMENT_CHAR_LIMIT].strip()
            
            if relevant_text:
                extracted_parts.append(f"[{doc['category'].upper()}] {path}\n{relevant_text}")

    if rag_context:
        extracted_parts.insert(0, f"[RAG] Semantic retrieval context\n{rag_context}")

    combined_text = "\n\n".join(extracted_parts).strip()
    if not combined_text:
        return ""

    limited_text = combined_text[:MAX_INPUT_CHARS]
    return generate_summary(limited_text, normalized_role, query=query)
