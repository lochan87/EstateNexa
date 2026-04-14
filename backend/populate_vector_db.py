"""
Script to populate ChromaDB vector database with document chunks
Reads PDFs, chunks them, and stores in ChromaDB (local vector DB)
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.document_loader import DocumentLoader

DOCUMENT_ACCESS_ROLE_MAP = {
    "Property_Listings.pdf": "buyer",
    "Investment_Insights.pdf": "agent",
    "Market_Analysis_ Report.pdf": "agent",
    "Financial_Investment_Data.pdf": "agent",
    "Bangalore_Location_Intelligence_Report.pdf": "buyer",
    "legal_documents.pdf": "admin",
}

ACCESS_POLICY_MAP = {
    "admin": ["admin"],
    "agent": ["admin", "agent"],
    "buyer": ["admin", "agent", "buyer"],
}


def populate_chromadb():
    """Load documents, chunk them, and store in ChromaDB"""
    print("\n" + "=" * 60)
    print("  Populating ChromaDB Vector Database")
    print("=" * 60)

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Initialize ChromaDB
    print("\n🔍 Initializing ChromaDB...")
    try:
        from backend.chroma_store import get_chroma_store
        vector_store = get_chroma_store()
    except Exception as e:
        print(f"✗ ChromaDB initialization failed: {str(e)}")
        return False

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Initialize document loaders
    print("📂 Initializing document loader...")
    legacy_documents_path = os.path.join(project_root, "Documents")
    investment_documents_path = os.path.join(project_root, "backend", "investment", "documents")
    legacy_loader = DocumentLoader(documents_path=legacy_documents_path)
    investment_loader = DocumentLoader(documents_path=investment_documents_path)

    # Load all documents
    print("📄 Loading documents from Documents and backend/investment/documents...")
    all_documents = {}
    if os.path.exists(legacy_documents_path):
        all_documents.update(legacy_loader.load_all_documents_in_directory())
    if os.path.exists(investment_documents_path):
        all_documents.update(investment_loader.load_all_documents_in_directory())

    if not all_documents:
        print("✗ No documents found in configured document folders")
        return False

    total_chunks = 0
    successful_uploads = 0

    # Upload each document's chunks
    for filename, chunks in all_documents.items():
        try:
            print(f"\n  Processing: {filename}")
            print(f"    - Chunks: {len(chunks)}")
            print(f"    - Total size: {sum(len(c.page_content) for c in chunks)} chars")

            if chunks:
                access_role = DOCUMENT_ACCESS_ROLE_MAP.get(filename, "buyer")
                allowed_roles = ACCESS_POLICY_MAP.get(access_role, ["admin", "agent", "buyer"])
                success = vector_store.add_documents(
                    chunks,
                    metadata_filter={
                        "source": filename,
                        "access_role": access_role,
                        "access_policies": ",".join(allowed_roles),
                    },
                )
                if success:
                    total_chunks += len(chunks)
                    successful_uploads += 1
                    print(f"    ✓ Uploaded {len(chunks)} chunks")
                else:
                    print(f"    ✗ Failed to upload chunks")

        except Exception as e:
            print(f"    ✗ Error processing {filename}: {str(e)}")

    # Persist to disk
    vector_store.persist()

    # Get index statistics
    print("\n📊 Collection Statistics:")
    stats = vector_store.get_collection_stats()
    if stats:
        print(f"  - Collection: {stats.get('collection_name', 'N/A')}")
        print(f"  - Documents: {stats.get('document_count', 0)}")
        print(f"  - Persist directory: {stats.get('persist_directory', 'N/A')}")

    print("\n" + "=" * 60)
    print(f"✅ Vector DB population completed!")
    print(f"   - Documents processed: {successful_uploads}")
    print(f"   - Total chunks stored: {total_chunks}")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = populate_chromadb()
    sys.exit(0 if success else 1)
