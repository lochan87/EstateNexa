import csv
import json
import re
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document
from pypdf import PdfReader

from rag.vector_store import upsert_property_documents

SENSITIVE_METADATA_FIELDS = {"actual_price"}


def _to_float(value: str | int | float | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_number_from_text(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = re.sub(r"[^0-9.]", "", value)
    return _to_float(cleaned)


def _normalize_pdf_record(raw: dict[str, str]) -> dict:
    area = raw.get("area") or raw.get("location")
    city = raw.get("city")
    location = f"{area}, {city}" if area and city else (area or city)

    agent_details = {
        "agent_id": raw.get("agent id"),
        "agent_name": raw.get("agent name"),
        "agent_contact": raw.get("agent contact"),
        "agency_name": raw.get("agency name"),
        "experience_years": raw.get("agent experience (years)"),
    }

    return {
        "property_id": raw.get("property id"),
        "location": location,
        "actual_price": _to_number_from_text(raw.get("actual price (inr)")),
        "quoted_price": _to_number_from_text(raw.get("quoted price (inr)")),
        "bedrooms": _to_number_from_text(raw.get("bedrooms")),
        "property_type": raw.get("property type"),
        "amenities": raw.get("amenities", ""),
        "description": raw.get("description", ""),
        "agent_details": json.dumps(agent_details),
    }


def _parse_property_records_from_pdf_text(text: str) -> list[dict]:
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    current_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "property id":
                if current:
                    records.append(current)
                current = {}

            if current or key == "property id":
                current[key] = value
                current_key = key
            continue

        if current and current_key:
            current[current_key] = f"{current[current_key]} {line}".strip()

    if current:
        records.append(current)

    return [_normalize_pdf_record(row) for row in records if row.get("property id")]


def build_property_document(record: dict) -> Document:
    property_id = str(record.get("property_id", ""))
    location = record.get("location")
    actual_price = _to_float(record.get("actual_price"))
    quoted_price = _to_float(record.get("quoted_price"))
    bedrooms_value = record.get("bedrooms")
    bedrooms = int(float(bedrooms_value)) if bedrooms_value not in (None, "") else None
    property_type = record.get("property_type")
    amenities = record.get("amenities") or []
    description = record.get("description") or ""
    agent_details = record.get("agent details") or record.get("agent_details") or ""

    if isinstance(amenities, str):
        amenities = [a.strip() for a in amenities.split(",") if a.strip()]

    page_content = (
        f"Property {property_id} in {location}. "
        f"Type: {property_type}. Bedrooms: {bedrooms}. "
        f"Amenities: {', '.join(amenities)}. "
        f"Description: {description}. "
        f"Agent details: {agent_details}."
    )

    metadata = {
        "property_id": property_id,
        "location": location,
        "actual_price": actual_price,
        "quoted_price": quoted_price,
        "bedrooms": bedrooms,
        "property_type": property_type,
        "amenities": amenities,
        "sensitive_tags": sorted(SENSITIVE_METADATA_FIELDS),
    }

    return Document(page_content=page_content, metadata=metadata)


def load_records(dataset_path: str | Path) -> list[dict]:
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        records = _parse_property_records_from_pdf_text(full_text)
        if not records:
            raise ValueError("No property records found in PDF. Verify Property ID/key-value formatting.")
        return records

    raise ValueError("Only JSON, CSV, and PDF datasets are supported")


def ingest_property_dataset(dataset_path: str | Path) -> int:
    records = load_records(dataset_path)
    docs = [build_property_document(record) for record in records]
    upsert_property_documents(docs)
    return len(docs)


def ingest_property_records(records: Iterable[dict]) -> int:
    docs = [build_property_document(record) for record in records]
    upsert_property_documents(docs)
    return len(docs)
