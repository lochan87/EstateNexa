from __future__ import annotations

from typing import Any

from langchain_core.documents import Document


RESTRICTED_BUYER_FIELDS = {
    "actual_price",
    "agent_id",
    "agent_name",
    "agent_contact",
    "agency_name",
    "agent_experience",
}


def _normalize_role(role: str) -> str:
    normalized = (role or "").strip().lower()
    if normalized not in {"buyer", "agent", "admin"}:
        raise ValueError(f"Unsupported role: {role}")
    return normalized


def _safe_property_context(metadata: dict[str, Any], role: str) -> str:
    lines = [
        f"Property ID: {metadata.get('property_id', '')}",
        f"Area: {metadata.get('area', '')}",
    ]

    if role in {"agent", "admin"}:
        lines.extend(
            [
                f"Agent ID: {metadata.get('agent_id', '')}",
                f"Agent Name: {metadata.get('agent_name', '')}",
                f"Agent Contact: {metadata.get('agent_contact', '')}",
                f"Agency Name: {metadata.get('agency_name', '')}",
                f"Agent Experience (years): {metadata.get('agent_experience', '')}",
                f"Actual Price (INR): {metadata.get('actual_price', '')}",
            ]
        )

    lines.extend(
        [
            f"Quoted Price (INR): {metadata.get('quoted_price', '')}",
            f"Size (sq ft): {metadata.get('size_sq_ft', '')}",
            f"Bedrooms: {metadata.get('bedrooms', '')}",
            f"Amenities: {metadata.get('amenities', '')}",
            f"Property Type: {metadata.get('property_type', '')}",
            f"Availability Status: {metadata.get('availability_status', '')}",
            f"Nearby Locations: {metadata.get('nearby_locations', '')}",
            f"Description: {metadata.get('description', '')}",
        ]
    )
    return "\n".join(lines)


def filter_documents_for_role(
    documents: list[Document],
    user_role: str,
    user_agent_id: str | None = None,
) -> list[dict[str, Any]]:
    role = _normalize_role(user_role)
    filtered: list[dict[str, Any]] = []

    for doc in documents:
        metadata = dict(doc.metadata or {})
        source = metadata.get("source")

        if source == "location":
            filtered.append(
                {
                    "source": "location",
                    "area": metadata.get("area"),
                    "content": doc.page_content,
                    "metadata": {"area": metadata.get("area")},
                }
            )
            continue

        if source != "property_listing":
            continue

        if role == "agent":
            if not user_agent_id:
                continue
            if str(metadata.get("agent_id", "")).strip() != str(user_agent_id).strip():
                continue

        visible_metadata = {key: value for key, value in metadata.items() if key not in RESTRICTED_BUYER_FIELDS}
        if role in {"agent", "admin"}:
            visible_metadata = metadata

        filtered.append(
            {
                "source": "property_listing",
                "area": metadata.get("area"),
                "content": _safe_property_context(metadata, role),
                "metadata": visible_metadata,
            }
        )

    return filtered

