# EstateNexa Project Documentation

## 1. What This Project Is
EstateNexa is a role-aware real estate assistant backend. It helps users search properties semantically, apply structured filters, enforce data visibility by role, and generate document summaries from real estate PDFs.

Primary user roles:
- Buyer
- Agent
- Admin

The system is currently backend-focused and API-driven, with strong emphasis on:
- Property retrieval using vector search
- Role-based response security
- Summarization over local PDF knowledge sources

## 2. High-Level Architecture
The project is organized into these layers:

1. API Layer (FastAPI)
- Authentication endpoints
- Property retrieval endpoints
- Summarization endpoints

2. Intelligence Layer
- Vector search retrieval logic
- Intent detection (price/location/comparison/investment/full)
- Role-aware output shaping
- LLM summary generation using Groq (with fallback)

3. Data Layer
- PostgreSQL for users, sessions, responses, properties, and analysis data
- Chroma vector store for semantic property search
- Local PDFs in Documents for summarization context

4. Security Layer
- JWT-based auth
- Strict role normalization and response filtering

## 3. Repository Structure

Top-level folders:
- backend: FastAPI app, RAG logic, summarization modules, tests
- database: SQL schema and SQL migration/update scripts
- Documents: Domain PDF files used for summarization and references

Important files:
- backend/main.py: FastAPI app bootstrap and router registration
- backend/auth.py: authentication, JWT, DB connection utilities
- backend/rag/api.py: property retrieval API endpoint
- backend/rag/retrieval.py: core retrieval + intent + filtering logic
- backend/rag/security.py: role enforcement and field-level output control
- backend/rag/vector_store.py: embedding setup and Chroma persistence
- backend/rag/ingestion.py: dataset parsing and vector ingestion
- backend/routes/summarization.py: summarization endpoint and DB write-back
- backend/summarization/summarization_tool.py: document selection + relevance extraction + RAG context blend
- backend/summarization/summarizer.py: Groq-powered summary generation
- database/schema.sql: core relational model
- requirements.txt: Python dependencies

## 4. Tech Stack

Backend:
- FastAPI
- Uvicorn
- Pydantic

Security/Auth:
- python-jose (JWT)
- passlib

Database:
- PostgreSQL (via psycopg2-binary)

AI / Retrieval:
- LangChain core/community
- ChromaDB
- Sentence Transformers (configurable)
- Local hash embedding fallback (offline-safe)

Summarization:
- Groq API (LLaMA models) with fallback summarization path
- PDF parsing libraries (currently mixed usage in code: pypdf and PyPDF2)

Testing:
- pytest

Environment:
- python-dotenv

## 5. Data Model (PostgreSQL)
Defined in database/schema.sql.

Core tables:
1. users
- stores profile, role, credentials hash

2. chat_sessions
- groups interactions by user session

3. ai_responses
- stores generated outputs and tool provenance

4. documents
- metadata for documents with role-based accessibility

5. properties
- structured property facts and linked agent

6. agent_properties
- assignment mapping between agent and property

7. user_preferences
- preference profile for personalization

8. investment_analysis
- ROI, yield, risk, and detailed analysis payloads

## 6. Runtime Flow

### 6.1 Authentication Flow
1. User registers/logs in using backend/auth.py routes.
2. API returns JWT token and role.
3. Protected routes decode token and use role in authorization checks.

### 6.2 Property Retrieval Flow (RAG)
1. Request hits /rag/properties/search.
2. Role from token is validated against role in payload.
3. Query intent is detected (price/location/comparison/investment/full).
4. Location may be inferred from query text (including typo alias handling).
5. Vector similarity search runs in Chroma.
6. Results are role-filtered:
- Buyer: sees quoted price only
- Agent: sees actual + quoted price
- Admin: sees expanded admin fields
7. Response is reduced by intent and returned in minimal shape.

### 6.3 Summarization Flow
1. Request hits /summarize.
2. Role determines allowed PDF categories:
- Buyer: market + property
- Agent: market + property + financial
- Admin: market + property + financial + legal
3. Query keywords extract relevant sections from selected PDFs.
4. Optional semantic context from RAG retrieval is prepended.
5. Combined context is sent to Groq model for concise summary.
6. If Groq key/client unavailable, fallback local truncated summary is returned.
7. Response is persisted into chat_sessions + ai_responses.

## 7. API Endpoints

### Public/Health
- GET /
- GET /health

### Authentication
- POST /auth/register
- POST /auth/login
- POST /auth/logout

### Property Retrieval
- POST /rag/properties/search

### Summarization
- POST /summarize/

## 8. Role-Based Access Behavior
Centralized in backend/rag/security.py.

Rules:
- Role must be one of buyer/agent/admin.
- Output fields are generated from an explicit allowlist.
- Sensitive details are not leaked to unauthorized roles.

Practical effect:
- Buyer responses never contain actual_price, agent_contact, or internal_notes.
- Agent gets broader pricing visibility but still no admin-only internals.
- Admin can receive admin_fields payload.

## 9. Data Ingestion for Vector Search
Implemented in backend/rag/ingestion.py and backend/rag/ingest_properties.py.

Supported dataset formats:
- JSON
- CSV
- PDF

Ingestion steps:
1. Load records
2. Normalize property fields
3. Build LangChain Document objects
4. Upsert into Chroma vector store

CLI usage (from backend folder):
python -m rag.ingest_properties --dataset <path_to_csv_json_or_pdf>

## 10. Configuration and Environment Variables
Important variables used in code:
- DB_HOST
- DB_PORT
- DB_NAME
- DB_USER
- DB_PASSWORD
- JWT_SECRET_KEY
- JWT_ALGORITHM
- ACCESS_TOKEN_EXPIRE_MINUTES
- GROQ_API_KEY
- GROQ_MODEL
- VECTOR_DB_DIR
- EMBEDDING_PROVIDER
- EMBEDDING_DIMENSION
- EMBEDDING_MODEL_NAME
- PROPERTY_COLLECTION_NAME

## 11. Setup and Run

1. Create and activate virtual environment.
2. Install dependencies:
pip install -r requirements.txt

3. Create .env with DB/JWT/Groq values.

4. Ensure PostgreSQL has schema loaded:
- Execute database/schema.sql
- Optionally execute database/altered_cols.sql and database/updated_data.sql

5. Start API (from backend folder):
uvicorn main:app --reload

6. Open docs:
- Swagger UI: /docs

## 12. Testing
Current automated tests are in backend/tests/test_property_retrieval.py.

Coverage highlights:
- Role-based field filtering behavior
- Intent formatting behavior
- Location inference and typo handling
- Buyer/agent/admin response constraints

Run tests (from project root):
pytest

## 13. Current Strengths
- Strong role-based output enforcement
- Intent-aware response shaping for practical UX
- Hybrid summarization context: PDF + semantic retrieval
- Offline-capable embedding fallback path
- Clear modular separation between API, retrieval, and security logic

## 14. Known Gaps / Risks
1. PDF parser mismatch in current codebase
- summarization/pdf_reader.py imports PyPDF2 while requirements.txt lists pypdf.
- This may break summarization depending on environment package state.

2. Frontend is described in README but not present in this repository snapshot.

3. No full integration tests for end-to-end API workflows yet.

4. Database connectivity defaults point to a specific network host, which may fail outside that network.

## 15. Suggested Next Improvements
1. Unify PDF parsing dependency (choose one library and align code + requirements).
2. Add endpoint-level integration tests (auth + retrieval + summarize flows).
3. Add database migration tooling (Alembic) for versioned schema changes.
4. Add architecture diagram and sequence diagrams in docs.
5. Add deployment guide (Docker, env matrix, production hardening checklist).

---

This document is intended as the single onboarding reference for new contributors, reviewers, and stakeholders.
