from copy import deepcopy
from typing import Any


ALLOWED_ROLES = {"buyer", "agent", "admin"}
BASE_OUTPUT_FIELDS = ("property_id", "location", "visible_price", "bedrooms", "property_type", "highlights", "summary")
ADMIN_ONLY_FIELDS = ("agent_contact", "internal_notes", "sensitive_tags")


def normalize_role(role: str | None) -> str:
    if role is None:
        raise ValueError("user_role is required")

    normalized = str(role).strip().lower()
    if normalized not in ALLOWED_ROLES:
        raise ValueError(f"Unsupported role: {role}")
    return normalized


def _build_visible_price(item: dict[str, Any], role: str) -> dict[str, Any]:
    if role == "buyer":
        return {"quoted_price": item.get("quoted_price")}

    return {
        "actual_price": item.get("actual_price"),
        "quoted_price": item.get("quoted_price"),
    }


def _build_allowed_output(item: dict[str, Any], role: str) -> dict[str, Any]:
    allowed = {field: item.get(field) for field in BASE_OUTPUT_FIELDS if field != "visible_price"}
    allowed["visible_price"] = _build_visible_price(item, role)

    if role == "admin":
        admin_fields = {field: item.get(field) for field in ADMIN_ONLY_FIELDS if field in item}
        if admin_fields:
            allowed["admin_fields"] = admin_fields

    return allowed


def apply_role_based_filter(data: list[dict[str, Any]], user_role: str | None) -> list[dict[str, Any]]:
    """Return a strict role-filtered response using explicit field whitelisting."""
    normalized_role = normalize_role(user_role)
    sanitized = deepcopy(data)

    filtered: list[dict[str, Any]] = []
    for item in sanitized:
        filtered_item = _build_allowed_output(item, normalized_role)

        if normalized_role == "buyer":
            assert "actual_price" not in filtered_item
            assert "agent_contact" not in filtered_item
            assert "internal_notes" not in filtered_item

        if normalized_role == "agent":
            assert "agent_contact" not in filtered_item
            assert "internal_notes" not in filtered_item

        filtered.append(filtered_item)

    return filtered


def filter_sensitive_fields(data: list[dict[str, Any]], role: str | None) -> list[dict[str, Any]]:
    """Backward-compatible alias for role-based filtering."""
    return apply_role_based_filter(data, role)
