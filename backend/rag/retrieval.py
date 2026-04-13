from __future__ import annotations

import re
from difflib import get_close_matches
from typing import Any

from langchain_community.vectorstores import Chroma

from rag.models import PropertyFilters
from rag.security import apply_role_based_filter, normalize_role
from rag.vector_store import get_property_vector_store


INTENT_KEYWORDS = {
    "price_query": ("price", "cost", "quoted price", "actual price", "how much"),
    "location_query": ("location", "where", "area", "locality", "near"),
    "comparison_query": ("compare", "comparison", "vs", "versus", "difference"),
    "investment_query": ("invest", "investment", "roi", "return", "yield", "appreciation"),
}


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


def detect_intent(query: str) -> str:
    """Classify the user's request into a deterministic intent bucket."""
    normalized = _normalize_text(query)

    if not normalized:
        return "full_details"

    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return intent

    return "full_details"


def _deduplicate_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduplicated: list[dict[str, Any]] = []

    for item in results:
        property_id = str(item.get("property_id", "")).strip()
        if not property_id or property_id in seen:
            continue
        seen.add(property_id)
        deduplicated.append(item)

    return deduplicated


def _is_specific_query(query: str, intent: str) -> bool:
    normalized = _normalize_text(query)
    if intent == "price_query":
        return True

    specificity_markers = (
        "exact",
        "specific",
        "only",
        "single",
        "one",
        "best",
        "top",
        "price",
    )
    return any(marker in normalized for marker in specificity_markers)


def _truncate_results(results: list[dict[str, Any]], query: str, intent: str) -> list[dict[str, Any]]:
    limit = 1 if _is_specific_query(query, intent) else 2
    return results[:limit]


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
        "agent_contact": metadata.get("agent_contact"),
        "internal_notes": metadata.get("internal_notes"),
        "bedrooms": metadata.get("bedrooms"),
        "property_type": metadata.get("property_type"),
        "highlights": _highlights(metadata, query),
        "summary": doc.page_content[:350],
        "sensitive_tags": metadata.get("sensitive_tags", []),
    }

    return apply_role_based_filter([result], role)[0]


def format_response_by_intent(results: list[dict[str, Any]], intent: str, role: str) -> list[dict[str, Any]]:
    """Shape already role-filtered results into a minimal, intent-aware payload."""
    normalized_role = normalize_role(role)
    normalized_intent = (intent or "full_details").strip().lower()

    formatted: list[dict[str, Any]] = []
    for item in results:
        base = {
            "property_id": item.get("property_id"),
            "location": item.get("location"),
            "property_type": item.get("property_type"),
        }

        visible_price = item.get("visible_price")
        if visible_price is None and "price" in item:
            visible_price = item.get("price")

        if normalized_intent == "price_query":
            formatted.append({
                **base,
                "price": visible_price,
            })
            continue

        if normalized_intent == "location_query":
            formatted.append(base)
            continue

        if normalized_intent == "comparison_query":
            formatted.append({
                **base,
                "visible_price": visible_price,
                "bedrooms": item.get("bedrooms"),
                "highlights": item.get("highlights", [])[:2],
            })
            continue

        if normalized_intent == "investment_query":
            formatted.append({
                **base,
                "visible_price": visible_price,
                "bedrooms": item.get("bedrooms"),
                "highlights": item.get("highlights", [])[:2],
            })
            continue

        formatted_item = {
            **base,
            "visible_price": visible_price,
            "bedrooms": item.get("bedrooms"),
            "highlights": item.get("highlights", []),
            "summary": item.get("summary"),
        }

        if normalized_role == "admin" and item.get("admin_fields"):
            formatted_item["admin_fields"] = item.get("admin_fields")

        formatted.append(formatted_item)

    return formatted


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
    intent = detect_intent(query)
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

    results = [_format_result(doc, score, role, query) for doc, score in ranked]
    results = _deduplicate_results(results)
    results = _truncate_results(results, query=query, intent=intent)
    results = format_response_by_intent(results, intent=intent, role=role)

    for item in results:
        assert "actual_price" not in item
        assert "quoted_price" not in item
        assert "agent_contact" not in item
        assert "internal_notes" not in item

    return results
