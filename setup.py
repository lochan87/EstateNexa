#!/usr/bin/env python3
"""
Complete EstateNexa Database & Vector DB Setup
Runs all initialization steps in the correct order
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step_num, title, description=""):
    """Print a step header"""
    print(f"\n{'─' * 70}")
    print(f"Step {step_num}: {title}")
    if description:
        print(f"  {description}")
    print("─" * 70)


def check_env_file():
    """Check if .env file exists and is configured"""
    print_step(1, "Checking Environment Configuration")

    env_path = Path(".env")

    if not env_path.exists():
        print("✗ .env file not found")
        print("  Creating .env from .env.example...")
        example_path = Path(".env.example")
        if example_path.exists():
            import shutil
            shutil.copy(".env.example", ".env")
            print("✓ Created .env file")
            print("  ⚠ Update .env with your API keys before running db population")
        else:
            print("✗ .env.example not found")
            return False
    else:
        print("✓ .env file exists")

    # Load and check critical variables
    from dotenv import load_dotenv
    load_dotenv()

    checks = {
        "DB_HOST": "PostgreSQL Host",
        "DB_PORT": "PostgreSQL Port",
        "DB_NAME": "PostgreSQL Database",
        "DB_USER": "PostgreSQL User",
        "GROQ_API_KEY": "Groq API Key (for Investment Tool)",
    }

    optional_checks = {
        "PINECONE_API_KEY": "Pinecone API Key (for Vector DB)",
        "OPENAI_API_KEY": "OpenAI API Key (for Embeddings)",
    }

    all_ok = True
    print("\nRequired Configuration:")
    for key, desc in checks.items():
        value = os.getenv(key)
        if value and value != f"your_{key.lower()}_here":
            print(f"  ✓ {desc}")
        else:
            print(f"  ✗ {desc} - Missing or placeholder value")
            all_ok = False

    print("\nOptional Configuration:")
    for key, desc in optional_checks.items():
        value = os.getenv(key)
        if value and value != f"your_{key.lower()}_here":
            print(f"  ✓ {desc}")
        else:
            print(f"  ⚠ {desc} - Not configured (some features will be limited)")

    return all_ok


def install_dependencies():
    """Install Python dependencies"""
    print_step(2, "Installing Dependencies")

    try:
        print("Installing from requirements.txt...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"],
            check=True,
            capture_output=True,
            text=True,
        )
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error installing dependencies: {e.stderr}")
        return False


def run_db_migrations():
    """Run database migrations and populate PostgreSQL"""
    print_step(3, "Running Database Migrations", "Creating tables and populating PostgreSQL")

    try:
        print("Running db_init.py...")
        result = subprocess.run(
            [sys.executable, "backend/db_init.py"],
            check=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr)
        print("✓ Database migrations completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error running migrations: {e.stderr}")
        return False
    except FileNotFoundError:
        print("✗ backend/db_init.py not found")
        return False


def populate_vector_db():
    """Populate ChromaDB vector database"""
    print_step(4, "Populating Vector Database", "Uploading documents to ChromaDB (local)")

    try:
        print("Running populate_vector_db.py...")
        result = subprocess.run(
            [sys.executable, "backend/populate_vector_db.py"],
            check=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr)
        print("✓ Vector database populated successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error populating vector DB: {e.stderr}")
        return False
    except FileNotFoundError:
        print("⚠ backend/populate_vector_db.py not found (skipping)")
        return False


def verify_setup():
    """Verify the complete setup"""
    print_step(5, "Verifying Setup")

    try:
        from backend.database import SessionLocal
        from backend.models import User, Document, Property

        session = SessionLocal()
        users = session.query(User).count()
        docs = session.query(Document).count()
        props = session.query(Property).count()
        session.close()

        print(f"✓ PostgreSQL Database:")
        print(f"  - Users: {users}")
        print(f"  - Documents: {docs}")
        print(f"  - Properties: {props}")

        # Try to access ChromaDB
        try:
            from backend.chroma_store import get_chroma_store
            vector_store = get_chroma_store()
            stats = vector_store.get_collection_stats()
            print(f"\n✓ ChromaDB Vector Database:")
            print(f"  - Collection: {stats.get('collection_name')}")
            print(f"  - Documents stored: {stats.get('document_count')}")
            print(f"  - Persist directory: {stats.get('persist_directory')}")
        except Exception as e:
            print(f"\n⚠ ChromaDB check: {str(e)}")

        return True
    except Exception as e:
        print(f"✗ Verification failed: {str(e)}")
        return False


def print_next_steps():
    """Print next steps for the user"""
    print_header("Setup Complete! Next Steps")

    print("""
1. Start the FastAPI server:
   cd backend
   uvicorn main:app --reload

2. Access the API:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
   - Health check: http://localhost:8000/health

3. Test the Investment API:
   - First, login via /auth/login endpoint
   - Then use the /investment/analyze endpoint
   - Query example: "where could i invest for maximum returns"

4. Available endpoints:
   - POST /auth/register - Register new user
   - POST /auth/login - Login and get JWT token
   - POST /auth/logout - Logout
   - POST /investment/analyze - Analyze investment opportunities
   - GET /investment/analyze/history - Get analysis history
   - GET /investment/documents/available - Available documents

5. Database Information:
   - PostgreSQL: Documents and Properties metadata stored
   - ChromaDB: Document chunks for semantic search (local, no API keys)
   - Both linked via Document table

6. Database Files:
   - PostgreSQL: Running on 172.25.81.34:5432
   - ChromaDB: Stored in ./chroma_db/ directory

For full API documentation, see:
http://localhost:8000/docs (after starting server)
""")


def main():
    """Run complete setup"""
    print_header("EstateNexa - Complete Database & Vector DB Setup")

    # Change to project root if needed
    if Path("backend").exists():
        os.chdir(Path(__file__).parent)

    steps = [
        ("Environment Check", check_env_file),
        ("Dependency Installation", install_dependencies),
        ("Database Migrations", run_db_migrations),
        ("Vector DB Population", populate_vector_db),
        ("Verification", verify_setup),
    ]

    results = []

    for step_name, step_func in steps:
        try:
            result = step_func()
            results.append((step_name, result))
            if not result:
                print(f"\n⚠ {step_name} had issues but continuing...")
        except Exception as e:
            print(f"\n✗ Unexpected error in {step_name}: {str(e)}")
            results.append((step_name, False))

    # Print summary
    print_header("Setup Summary")
    for step_name, result in results:
        status = "✓" if result else "✗"
        print(f"{status} {step_name}")

    all_success = all(result for _, result in results)

    if all_success:
        print_next_steps()
        print("\n✅ Setup completed successfully!\n")
        return 0
    else:
        print("\n⚠ Setup completed with some issues. Review the log above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
