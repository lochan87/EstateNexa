from __future__ import annotations

import re
from difflib import get_close_matches
from typing import Any

from langchain_community.vectorstores import Chroma

from rag.models import PropertyFilters
from rag.security import filter_sensitive_fields, normalize_role
from rag.vector_store import get_property_vector_store


KNOWN_LOCATIONS = {
    "whitefield": "Whitefield, Bangalore",
    "sarjapur": "Sarjapur, Bangalore",
    "indiranagar": "Indiranagar, Bangalore",
    "electronic city": "Electronic City, Bangalore",
    "koramangala": "Koramangala, Bangalore",
    "hsr layout": "HSR Layout, Bangalore",
    "hebbal": "Hebbal, Bangalore",
    "jayanagar": "Jayanagar, Bangalore",
    "marathahalli": "Marathahalli, Bangalore",
    "bellandur": "Bellandur, Bangalore",
}

LOCATION_ALIASES = {
    "whitefield": "whitefield",
    "white filed": "whitefield",
    "white field": "whitefield",
    "whitefiled": "whitefield",
    "whitefied": "whitefield",
}


def _infer_location_from_query(query: str) -> str | None:
    lowered = (query or "").lower()
    normalized = re.sub(r"\s+", " ", lowered).strip()

    for alias, location_key in LOCATION_ALIASES.items():
        if alias in normalized:
            return KNOWN_LOCATIONS[location_key]

    for key, canonical in KNOWN_LOCATIONS.items():
        if key in normalized:
            return canonical

    query_tokens = re.findall(r"[a-z]+", normalized)
    if query_tokens:
        matches = get_close_matches(" ".join(query_tokens), list(KNOWN_LOCATIONS.keys()), n=1, cutoff=0.86)
        if matches:
            return KNOWN_LOCATIONS[matches[0]]

    return None


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _matches_location(record_location: str | None, target_location: str) -> bool:
    record = _normalize_text(record_location)
    target = _normalize_text(target_location)
    return record == target or target in record


def _build_where_clause(filters: PropertyFilters, role: str, query: str) -> dict[str, Any] | None:
    role = normalize_role(role)
    clauses: list[dict[str, Any]] = []
    effective_location = filters.location or _infer_location_from_query(query)

    if effective_location:
        clauses.append({"location": effective_location})

    if filters.bedrooms is not None:
        clauses.append({"bedrooms": filters.bedrooms})

    if filters.property_type:
        clauses.append({"property_type": filters.property_type})

    if filters.budget is not None:
        budget_field = "quoted_price" if role == "buyer" else "actual_price"
        clauses.append({budget_field: {"$lte": filters.budget}})

    if not clauses:
        return None

    if len(clauses) == 1:
        return clauses[0]

    return {"$and": clauses}


def _highlights(metadata: dict[str, Any], query: str) -> list[str]:
    items = []
    if metadata.get("amenities"):
        amenities = metadata["amenities"]
        if isinstance(amenities, list):
            items.append(f"Amenities: {', '.join(amenities[:4])}")

    items.append(f"Best semantic match for: {query}")
    return items


def _format_result(doc, score: float, role: str, query: str) -> dict[str, Any]:
    metadata = doc.metadata or {}
    result = {
        "property_id": str(metadata.get("property_id", "")),
        "location": metadata.get("location"),
        "actual_price": metadata.get("actual_price"),
        "quoted_price": metadata.get("quoted_price"),
        "bedrooms": metadata.get("bedrooms"),
        "property_type": metadata.get("property_type"),
        "highlights": _highlights(metadata, query),
        "summary": doc.page_content[:350],
        "sensitive_tags": metadata.get("sensitive_tags", []),
    }

    sanitized = filter_sensitive_fields([result], role)[0]
    sanitized.pop("quoted_price", None)
    sanitized.pop("actual_price", None)
    return sanitized


def property_retrieval_tool(
    query: str,
    filters: PropertyFilters,
    user_role: str,
    top_k: int = 5,
    vector_store: Chroma | None = None,
) -> list[dict[str, Any]]:
    role = normalize_role(user_role)
    store = vector_store or get_property_vector_store()
    effective_location = filters.location or _infer_location_from_query(query)
    where = _build_where_clause(filters=filters, role=role, query=query)

    docs_with_scores = store.similarity_search_with_relevance_scores(
        query=query,
        k=top_k,
        filter=where,
    )

    ranked = sorted(docs_with_scores, key=lambda row: row[1], reverse=True)

    if effective_location:
        ranked = [
            row
            for row in ranked
            if _matches_location((row[0].metadata or {}).get("location"), effective_location)
        ]

    return [_format_result(doc, score, role, query) for doc, score in ranked]
