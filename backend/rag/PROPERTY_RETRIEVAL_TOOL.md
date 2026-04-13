# Property Retrieval Tool: Detailed Technical Guide

## 1. Purpose
The Property Retrieval Tool is the core retrieval engine for semantic property search in EstateNexa. It combines:
- Query understanding (intent + location inference)
- Hybrid filtering (semantic similarity + structured constraints)
- Strict role-based output security
- Response shaping based on user intent

Primary implementation file:
- backend/rag/retrieval.py

Related modules:
- backend/rag/security.py
- backend/rag/models.py
- backend/rag/langchain_tools.py
- backend/rag/api.py

## 2. Where It Is Used

### 2.1 Direct API usage
Endpoint:
- POST /rag/properties/search

Flow:
1. Request enters backend/rag/api.py.
2. user_role is validated using normalize_role.
3. Role from JWT token must match role in request payload.
4. property_retrieval_tool is executed.
5. Filtered and intent-shaped results are returned.

### 2.2 LangChain Tool usage
The tool is wrapped as a StructuredTool in backend/rag/langchain_tools.py:
- name: property_retrieval_tool
- function: _tool_runner

This allows agent workflows to call retrieval in a typed, validated way.

## 3. Function Signature and Inputs
Main function:

property_retrieval_tool(
    query: str,
    filters: PropertyFilters,
    user_role: str,
    top_k: int = 5,
    vector_store: Chroma | None = None,
) -> list[dict[str, Any]]

Input details:
1. query
- Natural-language request from user.
- Examples: price query, comparison query, investment query.

2. filters (PropertyFilters)
- budget: maximum budget threshold
- location: explicit location constraint
- bedrooms: bedroom count constraint
- property_type: apartment/villa/plot/etc.

3. user_role
- Must be one of buyer, agent, admin.
- Enforced via normalize_role.

4. top_k
- Initial number of semantic matches fetched from vector store.

5. vector_store
- Optional injected store (useful for testing with fake stores).
- Defaults to get_property_vector_store().

## 4. Internal Pipeline
The tool follows a deterministic, layered pipeline:

1. Normalize and validate role
2. Detect query intent
3. Infer effective location (if needed)
4. Build vector-store filter clause
5. Perform semantic similarity search
6. Rank results by relevance score
7. Post-filter by inferred/effective location
8. Convert raw doc metadata to role-safe result
9. Deduplicate by property_id
10. Truncate based on intent/query specificity
11. Shape output by intent
12. Assert no sensitive leakage

This staged approach makes behavior predictable, testable, and secure.

## 5. Intent Detection
Implemented via detect_intent(query).

Supported intents:
- price_query
- location_query
- comparison_query
- investment_query
- full_details (default fallback)

Keyword map is defined in INTENT_KEYWORDS and matched against normalized query text.

Why it matters:
- Controls output payload shape.
- Helps return concise data for narrow questions (for example price-only requests).

## 6. Location Inference and Typo Handling
Implemented through:
- _infer_location_from_query
- KNOWN_LOCATIONS
- LOCATION_ALIASES
- _matches_location

Capabilities:
1. Exact alias mapping
- Example: white filed -> Whitefield, Bangalore

2. Canonical keyword recognition
- Example: sarjapur -> Sarjapur, Bangalore

3. Fuzzy correction using difflib.get_close_matches
- Helps recover from minor typos.

Then _matches_location ensures only matching-area results survive post-filtering.

## 7. Structured Filter Construction
Built by _build_where_clause(filters, role, query).

Rules:
1. location
- Uses explicit filters.location if provided.
- Otherwise tries inferred location from query.

2. bedrooms
- Adds equality filter when provided.

3. property_type
- Adds type filter when provided.

4. budget
- Uses role-aware price field:
  - buyer -> quoted_price
  - agent/admin -> actual_price

When multiple constraints exist, they are combined with $and.

## 8. Semantic Search Layer
Vector search call:
- store.similarity_search_with_relevance_scores(query, k=top_k, filter=where)

Behavior:
- Retrieves top-k semantically similar documents.
- Applies filter clause at vector-store query stage.
- Results are sorted by relevance score descending.

## 9. Result Formatting and Role Security
Raw metadata is converted in _format_result and passed through apply_role_based_filter.

Raw metadata fields considered:
- property_id
- location
- actual_price
- quoted_price
- agent_contact
- internal_notes
- bedrooms
- property_type
- highlights
- summary
- sensitive_tags

Role security behavior (from backend/rag/security.py):
1. buyer
- visible_price contains quoted_price only
- sensitive/internal fields excluded

2. agent
- visible_price contains actual_price and quoted_price
- admin-only internals excluded

3. admin
- visible_price contains actual_price and quoted_price
- admin_fields may include agent_contact, internal_notes, sensitive_tags

The retrieval function also includes assertion checks to catch accidental leakage before returning.

## 10. Intent-Based Output Shaping
After security filtering, format_response_by_intent customizes the payload shape.

1. price_query
- Minimal payload:
  - property_id
  - location
  - property_type
  - price

2. location_query
- Location-only style payload:
  - property_id
  - location
  - property_type

3. comparison_query / investment_query
- Lean comparative payload:
  - property_id
  - location
  - property_type
  - visible_price
  - bedrooms
  - highlights (top 2)

4. full_details
- Rich payload:
  - property_id
  - location
  - property_type
  - visible_price
  - bedrooms
  - highlights
  - summary
  - admin_fields (admin only)

## 11. Deduplication and Truncation

### 11.1 Deduplication
_deduplicate_results removes duplicates by property_id to prevent repeated cards.

### 11.2 Truncation strategy
_truncate_results uses _is_specific_query:
- If specific question or price intent -> return 1 result
- Otherwise -> return top 2

This keeps responses concise and focused.

## 12. API Contract
Request model in backend/rag/models.py:
- PropertyRetrievalInput

Fields:
- query (required, min length 2)
- filters (optional, default empty)
- user_role (required at runtime; validation enforces role)

Example request:

{
  "query": "What is the price of apartment in Whitefield?",
  "filters": {
    "bedrooms": 2
  },
  "user_role": "buyer"
}

Example response shape (price_query for buyer):

{
  "count": 1,
  "results": [
    {
      "property_id": "P-404",
      "location": "Whitefield, Bangalore",
      "property_type": "Apartment",
      "price": {
        "quoted_price": 10400000
      }
    }
  ]
}

## 13. Error Handling

Handled conditions:
1. Invalid or missing user_role
- normalize_role raises ValueError
- API returns HTTP 400

2. Token role mismatch vs request role
- API returns HTTP 403

3. Retrieval-level ValueError
- API converts to HTTP 400

Security principle:
- Fail closed on role validation and enforce explicit role match with authenticated identity.

## 14. Testing Coverage
Primary tests are in backend/tests/test_property_retrieval.py.

Verified behaviors include:
- Buyer never sees actual_price
- Agent sees both price fields through visible_price
- Admin receives admin_fields
- Intent detection and minimal formatting for price_query
- Query-based location inference
- Typo correction (for example whitefiled -> whitefield)
- Rejection of malformed or missing roles

## 15. Extension Guidelines
If extending this tool, follow these guardrails:

1. Keep role checks central
- Add new sensitive fields only through allowlists in security.py.

2. Add intent keywords carefully
- Update INTENT_KEYWORDS and corresponding format branch.

3. Preserve deterministic output shape
- Frontends and downstream agents depend on stable keys.

4. Add tests with each behavioral change
- Especially for privacy-sensitive fields and intent formatting.

5. Maintain assertion fences
- Keep no-leak assertions after formatting.

## 16. Known Limitations
1. Intent detection is keyword-based (not model-based), so nuanced phrasing may map to full_details.
2. Location inference only covers configured known locations and fuzzy matching threshold.
3. Truncation to 1 or 2 results is conservative; may hide long-tail options for broad discovery queries.

## 17. Quick Debug Checklist
When output looks incorrect, check in this order:
1. Role mismatch or invalid role in request payload.
2. Filter clause produced by _build_where_clause.
3. Vector store has expected metadata fields.
4. Location inference and _matches_location behavior.
5. Intent classification branch and output formatter.
6. Final assertion guards for sensitive field leakage.

---

This document is intended for developers integrating, extending, or auditing the Property Retrieval Tool implementation.
