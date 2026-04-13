# Comparison Tool Setup

## What this module needs

- `langchain-groq` installed
- `psycopg2-binary` installed
- Groq API key
- PostgreSQL access for saving query/response logs
- Access to these two PDFs only:
  - `Property_Listings.pdf` or `Property_Listings (1).pdf`
  - `Bangalore_Location_Intelligence_Report.pdf`

## Environment variables

Use the project-level `.env.example` as reference.

- `GROQ_API_KEY`
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `COMPARISON_PROPERTY_PDF`
- `COMPARISON_LOCATION_PDF`
- `COMPARISON_CHROMA_DIR`
- `COMPARISON_COLLECTION_NAME`
- `COMPARISON_EMBEDDING_MODEL`

## Install

```powershell
pip install -r requirements.txt
```

If you use a project-level `.env` file, it will now be loaded automatically when FastAPI starts.

## Run the API

From the `backend` directory:

```powershell
uvicorn main:app --reload
```

## Swagger test flow

Open:

`http://127.0.0.1:8000/docs`

1. Run `POST /comparison/ingest`
2. Run `POST /comparison/compare`

Buyer example:

```json
{
  "query": "Compare Whitefield and Electronic City properties for investment",
  "user_role": "buyer",
  "user_agent_id": null
}
```

Agent example:

```json
{
  "query": "Compare Whitefield and Electronic City properties for investment",
  "user_role": "agent",
  "user_agent_id": "5"
}
```

Admin example:

```json
{
  "query": "Compare Whitefield and Electronic City properties for investment",
  "user_role": "admin",
  "user_agent_id": null
}
```

## Expected behavior

- Buyer cannot see actual price or agent details
- Agent can only see properties owned by the logged-in agent id
- Admin can see everything
- Query and generated answer are stored in `ai_responses`

## Common issues

- If embeddings fail on first run, internet access may be needed to download `sentence-transformers/all-MiniLM-L6-v2`
- If compare fails immediately, check `GROQ_API_KEY`
- If DB logging fails, verify PostgreSQL connection values
