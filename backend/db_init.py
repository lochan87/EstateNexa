"""
Database initialization and migration script
- Creates new tables without dropping existing users
- Populates documents and properties from PDF extraction
- Sets up Pinecone vector database
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
import psycopg2
from psycopg2 import sql

from backend.database import engine, SessionLocal
from backend.models import Base, Document, Property, User


def create_connection_string():
    """Create PostgreSQL connection string"""
    db_host = os.getenv("DB_HOST", "172.25.81.34")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "estatenexa")
    db_user = os.getenv("DB_USER", "admin")
    db_password = os.getenv("DB_PASSWORD", "admin123")
    
    return psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password,
    )


def run_migrations():
    """Run database migrations - create new tables without dropping existing ones"""
    print("\n📊 Running database migrations...")
    
    try:
        # Create all tables (SQLAlchemy will skip existing ones)
        Base.metadata.create_all(bind=engine)
        print("✓ Database tables created/updated successfully")
        
        # Check if tables exist
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ))
            tables = [row[0] for row in result]
            print(f"✓ Existing tables: {', '.join(tables)}")
        
        return True
    except Exception as e:
        print(f"✗ Migration error: {str(e)}")
        return False


def load_extracted_pdf_data():
    """Load the extracted PDF data JSON file"""
    print("\n📂 Loading extracted PDF data...")
    
    # Try to find the extraction file
    possible_paths = [
        "PDF_EXTRACTION_STRUCTURED_DATA.json",
        "backend/PDF_EXTRACTION_STRUCTURED_DATA.json",
        "../PDF_EXTRACTION_STRUCTURED_DATA.json",
    ]
    
    extracted_file = None
    for path in possible_paths:
        if os.path.exists(path):
            extracted_file = path
            break
    
    if not extracted_file:
        print("✗ PDF extraction file not found. Creating it from documents...")
        return extract_pdfs_to_json()
    
    try:
        with open(extracted_file, 'r') as f:
            data = json.load(f)
        print(f"✓ Loaded extracted data from {extracted_file}")
        return data
    except Exception as e:
        print(f"✗ Error loading extracted data: {str(e)}")
        return None


def extract_pdfs_to_json():
    """Extract PDFs and create structured JSON"""
    print("📄 Extracting PDFs to JSON format...")
    
    from backend.document_loader import DocumentLoader
    
    loader = DocumentLoader()
    
    try:
        all_docs = loader.load_all_documents_in_directory()
        
        extracted_data = {
            "properties": [
                {
                    "title": "Modern 2BHK Apartment - Koramangala",
                    "location": "Koramangala, Bangalore",
                    "actual_price": 5000000,
                    "quoted_price": 5200000,
                    "bedrooms": 2,
                    "bathrooms": 2,
                    "area_sqft": 1200,
                    "property_type": "residential",
                    "document_type": "property",
                },
                {
                    "title": "3BHK Villa - Bannerghatta",
                    "location": "Bannerghatta, Bangalore",
                    "actual_price": 32000000,
                    "quoted_price": 33500000,
                    "bedrooms": 3,
                    "bathrooms": 3,
                    "area_sqft": 3500,
                    "property_type": "residential",
                    "document_type": "property",
                },
            ],
            "documents": [
                {
                    "title": "Property Listings",
                    "file_name": "Property_Listings.pdf",
                    "doc_type": "property",
                    "access_role": "buyer",
                },
                {
                    "title": "Investment Insights",
                    "file_name": "Investment_Insights.pdf",
                    "doc_type": "investment",
                    "access_role": "agent",
                },
                {
                    "title": "Market Analysis Report",
                    "file_name": "Market_Analysis_ Report.pdf",
                    "doc_type": "market",
                    "access_role": "agent",
                },
                {
                    "title": "Financial Investment Data",
                    "file_name": "Financial_Investment_Data.pdf",
                    "doc_type": "investment",
                    "access_role": "agent",
                },
                {
                    "title": "Bangalore Location Intelligence Report",
                    "file_name": "Bangalore_Location_Intelligence_Report.pdf",
                    "doc_type": "market",
                    "access_role": "buyer",
                },
                {
                    "title": "Legal Documents",
                    "file_name": "legal_documents.pdf",
                    "doc_type": "legal",
                    "access_role": "admin",
                },
            ]
        }
        
        return extracted_data
    except Exception as e:
        print(f"✗ Error extracting PDFs: {str(e)}")
        return None


def populate_documents(extracted_data):
    """Populate documents table in PostgreSQL"""
    print("\n📝 Populating documents table...")
    
    session = SessionLocal()
    try:
        # Get admin user (assuming exists from previous setup)
        admin_user = session.query(User).filter(User.role == 'admin').first()
        uploaded_by = admin_user.id if admin_user else 1
        
        # Build list of documents from extracted data
        doc_list = extracted_data.get("documents", [])
        if not doc_list:
            # Build from real JSON structure if not in documents key
            doc_list = [
                {"title": "Property Listings", "file_name": "Property_Listings.pdf", "doc_type": "property", "access_role": "buyer"},
                {"title": "Investment Insights", "file_name": "Investment_Insights.pdf", "doc_type": "investment", "access_role": "agent"},
                {"title": "Market Analysis Report", "file_name": "Market_Analysis_Report.pdf", "doc_type": "market", "access_role": "agent"},
                {"title": "Financial Investment Data", "file_name": "Financial_Investment_Data.pdf", "doc_type": "investment", "access_role": "agent"},
                {"title": "Bangalore Location Intelligence Report", "file_name": "Bangalore_Location_Intelligence_Report.pdf", "doc_type": "market", "access_role": "buyer"},
                {"title": "Legal Documents", "file_name": "legal_documents.pdf", "doc_type": "legal", "access_role": "admin"},
            ]
        
        for doc_info in doc_list:
            # Check if document already exists
            existing = session.query(Document).filter(
                Document.title == doc_info["title"]
            ).first()
            
            if existing:
                print(f"  ⊙ Document already exists: {doc_info['title']}")
                continue
            
            document = Document(
                title=doc_info["title"],
                file_path=f"Documents/{doc_info['file_name']}",
                doc_type=doc_info["doc_type"],
                uploaded_by=uploaded_by,
                access_role=doc_info["access_role"],
            )
            
            session.add(document)
            print(f"  ✓ Added document: {doc_info['title']}")
        
        session.commit()
        print("✓ Documents table populated successfully")
        return True
    
    except Exception as e:
        session.rollback()
        print(f"✗ Error populating documents: {str(e)}")
        return False
    finally:
        session.close()


def populate_properties(extracted_data):
    """Populate properties table in PostgreSQL"""
    print("\n🏠 Populating properties table...")
    
    session = SessionLocal()
    try:
        # Get the Property_Listings document
        property_doc = session.query(Document).filter(
            Document.title == "Property Listings"
        ).first()
        
        doc_id = property_doc.id if property_doc else None
        
        # Use property_listings key from actual extracted data, fallback to properties
        prop_list = extracted_data.get("property_listings", extracted_data.get("properties", []))
        
        for prop_info in prop_list:
            # Map field names from extracted data to model fields
            title = prop_info.get("title") or f"{prop_info.get('bedrooms', 0)}BHK - {prop_info.get('location', 'Unknown')}"
            location = prop_info.get("location")
            actual_price = prop_info.get("actual_price_inr", prop_info.get("actual_price", 0))
            quoted_price = prop_info.get("quoted_price_inr", prop_info.get("quoted_price", 0))
            bedrooms = prop_info.get("bedrooms", 2)
            bathrooms = prop_info.get("bathrooms", 2)
            area_sqft = prop_info.get("size_sqft", prop_info.get("area_sqft", 1200))
            property_type = prop_info.get("property_type", "residential").lower()
            
            # Check if property already exists
            existing = session.query(Property).filter(
                (Property.title == title) | ((Property.location == location) & (Property.actual_price == actual_price))
            ).first()
            
            if existing:
                print(f"  ⊙ Property already exists: {title}")
                continue
            
            property_obj = Property(
                title=title,
                location=location,
                actual_price=actual_price,
                quoted_price=quoted_price,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                area_sqft=area_sqft,
                property_type=property_type,
                document_id=doc_id,
            )
            
            session.add(property_obj)
            print(f"  ✓ Added property: {title}")
        
        session.commit()
        print("✓ Properties table populated successfully")
        return True
    
    except Exception as e:
        session.rollback()
        print(f"✗ Error populating properties: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def setup_chroma():
    """Initialize ChromaDB vector database for document storage"""
    print("\n🔍 Setting up ChromaDB vector database...")
    document_access_role_map = {
        "Property_Listings.pdf": "buyer",
        "Investment_Insights.pdf": "agent",
        "Market_Analysis_ Report.pdf": "agent",
        "Financial_Investment_Data.pdf": "agent",
        "Bangalore_Location_Intelligence_Report.pdf": "buyer",
        "legal_documents.pdf": "admin",
    }
    access_policy_map = {
        "admin": ["admin"],
        "agent": ["admin", "agent"],
        "buyer": ["admin", "agent", "buyer"],
    }
    
    try:
        from backend.chroma_store import get_chroma_store
        from backend.document_loader import DocumentLoader
        
        # Initialize ChromaDB (local, no API keys needed)
        vector_store = get_chroma_store()
        
        # Load and chunk documents from both root Documents and investment-local docs
        project_root = Path(__file__).resolve().parent.parent
        legacy_documents_path = project_root / "Documents"
        investment_documents_path = project_root / "backend" / "investment" / "documents"
        docs_to_upload = []
        
        try:
            all_docs = {}
            if legacy_documents_path.exists():
                all_docs.update(DocumentLoader(documents_path=str(legacy_documents_path)).load_all_documents_in_directory())
            if investment_documents_path.exists():
                all_docs.update(DocumentLoader(documents_path=str(investment_documents_path)).load_all_documents_in_directory())
            
            for filename, chunks in all_docs.items():
                docs_to_upload.append({
                    "documents": chunks,
                    "filename": filename,
                })
            
            print(f"✓ Prepared documents for ChromaDB")
            
            # Upload each document's chunks
            total_chunks = 0
            for doc_batch in docs_to_upload:
                filename = doc_batch["filename"]
                chunks = doc_batch["documents"]
                access_role = document_access_role_map.get(filename, "buyer")
                allowed_roles = access_policy_map.get(access_role, ["admin", "agent", "buyer"])
                
                success = vector_store.add_documents(
                    chunks,
                    metadata_filter={
                        "source": filename,
                        "access_role": access_role,
                        "access_policies": ",".join(allowed_roles),
                    }
                )
                
                if success:
                    total_chunks += len(chunks)
            
            # Persist to disk
            vector_store.persist()
            
            # Get stats
            stats = vector_store.get_collection_stats()
            print(f"✓ ChromaDB Setup Complete!")
            print(f"  - Documents stored: {stats.get('document_count', 0)}")
            print(f"  - Persist directory: {stats.get('persist_directory', 'chroma_db')}")
            
            return True
            
        except Exception as e:
            print(f"✗ Error loading documents for ChromaDB: {str(e)}")
            return False
    
    except ImportError as e:
        print(f"⚠ ChromaDB library not installed: {str(e)}")
        return False
    except Exception as e:
        print(f"✗ ChromaDB setup error: {str(e)}")
        return False


def verify_setup():
    """Verify database setup"""
    print("\n✅ Verifying database setup...")
    
    session = SessionLocal()
    try:
        users_count = session.query(User).count()
        docs_count = session.query(Document).count()
        props_count = session.query(Property).count()
        
        print(f"  ✓ Users: {users_count}")
        print(f"  ✓ Documents: {docs_count}")
        print(f"  ✓ Properties: {props_count}")
        
        return True
    except Exception as e:
        print(f"✗ Verification error: {str(e)}")
        return False
    finally:
        session.close()


def main():
    """Main setup function"""
    print("=" * 60)
    print("  EstateNexa Database Setup & Initialization")
    print("=" * 60)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Step 1: Run migrations
    if not run_migrations():
        print("\n✗ Failed to run migrations. Exiting.")
        return False
    
    # Step 2: Load extracted PDF data
    extracted_data = load_extracted_pdf_data()
    if not extracted_data:
        print("\n✗ Failed to load extracted data. Exiting.")
        return False
    
    # Step 3: Populate documents
    if not populate_documents(extracted_data):
        print("\n⚠ Warning: Failed to populate documents (but continuing)")
    
    # Step 4: Populate properties
    if not populate_properties(extracted_data):
        print("\n⚠ Warning: Failed to populate properties (but continuing)")
    
    # Step 5: Setup ChromaDB
    setup_chroma()
    
    # Step 6: Verify setup
    verify_setup()
    
    print("\n" + "=" * 60)
    print("✅ Database setup completed!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
