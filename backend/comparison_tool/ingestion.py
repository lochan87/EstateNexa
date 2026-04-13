from __future__ import annotations

import re
from pathlib import Path

from langchain_core.documents import Document
from pypdf import PdfReader

try:
    from .config import get_settings
    from .vector_store import upsert_documents
except ImportError:
    from config import get_settings
    from vector_store import upsert_documents


PROPERTY_FIELDS = {
    "Property ID",
    "Agent ID",
    "Agent Name",
    "Agent Contact",
    "Agency Name",
    "Agent Experience (years)",
    "City",
    "Area",
    "Coordinates",
    "Actual Price (INR)",
    "Quoted Price (INR)",
    "Size (sq ft)",
    "Bedrooms",
    "Nearby Locations",
    "Amenities",
    "Property Type",
    "Availability Status",
    "Description",
}


def _read_pdf_text(pdf_path: Path) -> str:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    reader = PdfReader(str(pdf_path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _parse_key_value_block(block: str) -> dict[str, str]:
    data: dict[str, str] = {}
    current_key: str | None = None

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key in PROPERTY_FIELDS:
                data[key] = value
                current_key = key
                continue

        if current_key:
            data[current_key] = f"{data[current_key]} {line}".strip()

    return data


def parse_property_listing_pdf(pdf_path: Path) -> list[Document]:
    text = _read_pdf_text(pdf_path)
    matches = list(re.finditer(r"Property ID:\s*([A-Z0-9]+)", text))
    documents: list[Document] = []

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        record = _parse_key_value_block(block)
        property_id = record.get("Property ID")
        area = record.get("Area")
        agent_id = record.get("Agent ID")

        if not property_id or not area or not agent_id:
            continue

        content = "\n".join(
            [
                f"Property ID: {property_id}",
                f"Area: {area}",
                f"City: {record.get('City', '')}",
                f"Agent ID: {agent_id}",
                f"Agent Name: {record.get('Agent Name', '')}",
                f"Agent Contact: {record.get('Agent Contact', '')}",
                f"Agency Name: {record.get('Agency Name', '')}",
                f"Agent Experience (years): {record.get('Agent Experience (years)', '')}",
                f"Actual Price (INR): {record.get('Actual Price (INR)', '')}",
                f"Quoted Price (INR): {record.get('Quoted Price (INR)', '')}",
                f"Size (sq ft): {record.get('Size (sq ft)', '')}",
                f"Bedrooms: {record.get('Bedrooms', '')}",
                f"Amenities: {record.get('Amenities', '')}",
                f"Nearby Locations: {record.get('Nearby Locations', '')}",
                f"Property Type: {record.get('Property Type', '')}",
                f"Availability Status: {record.get('Availability Status', '')}",
                f"Description: {record.get('Description', '')}",
            ]
        )

        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source": "property_listing",
                    "area": area,
                    "property_id": property_id,
                    "agent_id": agent_id,
                    "agent_name": record.get("Agent Name", ""),
                    "agent_contact": record.get("Agent Contact", ""),
                    "agency_name": record.get("Agency Name", ""),
                    "agent_experience": record.get("Agent Experience (years)", ""),
                    "actual_price": record.get("Actual Price (INR)", ""),
                    "quoted_price": record.get("Quoted Price (INR)", ""),
                    "size_sq_ft": record.get("Size (sq ft)", ""),
                    "bedrooms": record.get("Bedrooms", ""),
                    "amenities": record.get("Amenities", ""),
                    "property_type": record.get("Property Type", ""),
                    "availability_status": record.get("Availability Status", ""),
                    "nearby_locations": record.get("Nearby Locations", ""),
                    "description": record.get("Description", ""),
                },
            )
        )

    return documents


def parse_location_intelligence_pdf(pdf_path: Path) -> list[Document]:
    text = _read_pdf_text(pdf_path)
    pattern = re.compile(r"LOCATION\s+\d+\s*:\s*([A-Z ]+)")
    matches = list(pattern.finditer(text))
    documents: list[Document] = []

    for index, match in enumerate(matches):
        area = " ".join(match.group(1).split()).title()
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()

        documents.append(
            Document(
                page_content=section_text,
                metadata={
                    "source": "location",
                    "area": area,
                },
            )
        )

    return documents


def ingest_documents() -> dict[str, int]:
    settings = get_settings()
    property_docs = parse_property_listing_pdf(settings.property_pdf_path)
    location_docs = parse_location_intelligence_pdf(settings.location_pdf_path)

    property_ids = [f"property::{doc.metadata['property_id']}" for doc in property_docs]
    location_ids = [f"location::{doc.metadata['area'].lower().replace(' ', '_')}" for doc in location_docs]

    upsert_documents(property_docs, property_ids)
    upsert_documents(location_docs, location_ids)

    return {
        "property_documents": len(property_docs),
        "location_documents": len(location_docs),
        "total_documents": len(property_docs) + len(location_docs),
    }

