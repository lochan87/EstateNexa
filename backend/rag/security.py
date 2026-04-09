from copy import deepcopy
from typing import Any


ALLOWED_ROLES = {"buyer", "agent", "admin"}
SENSITIVE_FIELDS = {"actual_price"}


def normalize_role(role: str) -> str:
    normalized = (role or "").strip().lower()
    if normalized not in ALLOWED_ROLES:
        raise ValueError(f"Unsupported role: {role}")
    return normalized


def filter_sensitive_fields(data: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    """Return a sanitized copy of retrieval results based on role."""
    normalized_role = normalize_role(role)
    sanitized = deepcopy(data)

    for item in sanitized:
        if normalized_role == "buyer":
            for field in SENSITIVE_FIELDS:
                item.pop(field, None)

            quoted_price = item.get("quoted_price")
            item["price"] = {"quoted_price": quoted_price}

        elif normalized_role in {"agent", "admin"}:
            item["price"] = {
                "actual_price": item.get("actual_price"),
                "quoted_price": item.get("quoted_price"),
            }

        if normalized_role != "admin":
            item.pop("sensitive_tags", None)

    return sanitized
