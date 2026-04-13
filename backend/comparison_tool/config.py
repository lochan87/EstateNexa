import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]


@dataclass(frozen=True)
class ComparisonToolSettings:
    property_pdf_path: Path
    location_pdf_path: Path
    chroma_dir: Path
    collection_name: str
    embedding_model_name: str
    groq_api_key: str | None
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    supported_locations: tuple[str, ...]


def _resolve_existing_path(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


@lru_cache(maxsize=1)
def get_settings() -> ComparisonToolSettings:
    property_pdf_path = _resolve_existing_path(
        Path(os.getenv("COMPARISON_PROPERTY_PDF", r"C:\Users\SHRIRAKSHA\Downloads\Property_Listings (1).pdf")),
        PROJECT_ROOT / "Documents" / "Property_Listings.pdf",
    )
    location_pdf_path = _resolve_existing_path(
        Path(
            os.getenv(
                "COMPARISON_LOCATION_PDF",
                r"C:\Users\SHRIRAKSHA\Downloads\Bangalore_Location_Intelligence_Report.pdf",
            )
        ),
        PROJECT_ROOT / "Documents" / "Bangalore_Location_Intelligence_Report.pdf",
    )

    return ComparisonToolSettings(
        property_pdf_path=property_pdf_path,
        location_pdf_path=location_pdf_path,
        chroma_dir=Path(os.getenv("COMPARISON_CHROMA_DIR", str(BASE_DIR / "data" / "chroma"))),
        collection_name=os.getenv("COMPARISON_COLLECTION_NAME", "real_estate_comparison"),
        embedding_model_name=os.getenv(
            "COMPARISON_EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        ),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        db_host=os.getenv("DB_HOST", "172.25.81.34"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_name=os.getenv("DB_NAME", "estatenexa"),
        db_user=os.getenv("DB_USER", "admin"),
        db_password=os.getenv("DB_PASSWORD", "admin123"),
        supported_locations=(
            "Whitefield",
            "Electronic City",
            "Sarjapur",
            "Marathahalli",
            "Yelahanka",
            "Hebbal",
            "HSR Layout",
            "Bellandur",
            "KR Puram",
            "Bannerghatta",
        ),
    )

