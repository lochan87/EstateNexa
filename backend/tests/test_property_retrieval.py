from langchain_core.documents import Document

from rag.models import PropertyFilters
from rag.retrieval import detect_intent, format_response_by_intent, property_retrieval_tool
from rag.security import apply_role_based_filter, filter_sensitive_fields


class FakeVectorStore:
    def __init__(self, docs_with_scores):
        self.docs_with_scores = docs_with_scores
        self.last_filter = None

    def similarity_search_with_relevance_scores(self, query, k, filter=None):
        self.last_filter = filter
        return self.docs_with_scores[:k]


def test_filter_sensitive_fields_buyer_hides_actual_price():
    data = [
        {
            "property_id": "P1",
            "location": "Whitefield, Bangalore",
            "actual_price": 100,
            "quoted_price": 110,
            "agent_contact": "+91-99999-99999",
            "internal_notes": "private",
            "bedrooms": 2,
            "property_type": "Apartment",
            "highlights": ["gym"],
            "summary": "summary",
        }
    ]
    out = apply_role_based_filter(data, user_role="buyer")
    assert set(out[0].keys()) == {"property_id", "location", "visible_price", "bedrooms", "property_type", "highlights", "summary"}
    assert out[0]["visible_price"] == {"quoted_price": 110}
    assert "actual_price" not in str(out[0])
    assert "agent_contact" not in str(out[0])


def test_property_retrieval_agent_gets_both_prices():
    fake_doc = Document(
        page_content="3BHK in Whitefield with metro access.",
        metadata={
            "property_id": "P-101",
            "location": "Whitefield",
            "actual_price": 9500000,
            "quoted_price": 9800000,
            "bedrooms": 3,
            "property_type": "apartment",
            "amenities": ["pool", "gym"],
            "sensitive_tags": ["actual_price"],
        },
    )
    store = FakeVectorStore([(fake_doc, 0.91)])

    results = property_retrieval_tool(
        query="3BHK Whitefield",
        filters=PropertyFilters(location="Whitefield", bedrooms=3),
        user_role="agent",
        vector_store=store,
    )

    assert len(results) == 1
    assert results[0]["visible_price"]["actual_price"] == 9500000
    assert results[0]["visible_price"]["quoted_price"] == 9800000
    assert "agent_contact" not in results[0]


def test_property_retrieval_buyer_never_sees_actual_price():
    fake_doc = Document(
        page_content="Villa in Sarjapur with garden.",
        metadata={
            "property_id": "P-202",
            "location": "Sarjapur",
            "actual_price": 15000000,
            "quoted_price": 15500000,
            "bedrooms": 4,
            "property_type": "villa",
            "amenities": ["garden", "clubhouse"],
            "sensitive_tags": ["actual_price"],
        },
    )
    store = FakeVectorStore([(fake_doc, 0.88)])

    results = property_retrieval_tool(
        query="villa with garden",
        filters=PropertyFilters(location="Sarjapur"),
        user_role="buyer",
        vector_store=store,
    )

    assert len(results) == 1
    assert "actual_price" not in str(results[0])
    assert results[0]["visible_price"] == {"quoted_price": 15500000}


def test_detect_intent_price_query():
    assert detect_intent("What is the price of Apartment in Sarjapur?") == "price_query"


def test_format_response_price_query_is_minimal():
    results = [
        {
            "property_id": "P-1",
            "location": "Sarjapur, Bangalore",
            "property_type": "Apartment",
            "visible_price": {"quoted_price": 12300000},
            "bedrooms": 3,
            "highlights": ["x"],
            "summary": "y",
        }
    ]

    formatted = format_response_by_intent(results, intent="price_query", role="buyer")

    assert formatted == [
        {
            "property_id": "P-1",
            "location": "Sarjapur, Bangalore",
            "property_type": "Apartment",
            "price": {"quoted_price": 12300000},
        }
    ]


def test_property_retrieval_admin_has_full_access():
    fake_doc = Document(
        page_content="Penthouse in Indiranagar.",
        metadata={
            "property_id": "P-303",
            "location": "Indiranagar",
            "actual_price": 26000000,
            "quoted_price": 27500000,
            "bedrooms": 4,
            "property_type": "penthouse",
            "amenities": ["terrace", "private lift"],
            "sensitive_tags": ["actual_price"],
        },
    )
    store = FakeVectorStore([(fake_doc, 0.96)])

    results = property_retrieval_tool(
        query="luxury penthouse",
        filters=PropertyFilters(property_type="penthouse"),
        user_role="admin",
        vector_store=store,
    )

    assert len(results) == 1
    assert results[0]["visible_price"]["actual_price"] == 26000000
    assert results[0]["visible_price"]["quoted_price"] == 27500000
    assert "admin_fields" in results[0]


def test_price_query_returns_only_minimal_fields():
    fake_doc = Document(
        page_content="Apartment in Sarjapur with garden.",
        metadata={
            "property_id": "P-505",
            "location": "Sarjapur, Bangalore",
            "actual_price": 12000000,
            "quoted_price": 12600000,
            "bedrooms": 3,
            "property_type": "Apartment",
            "amenities": ["garden", "pool"],
            "sensitive_tags": ["actual_price"],
        },
    )
    store = FakeVectorStore([(fake_doc, 0.99)])

    results = property_retrieval_tool(
        query="What is the price of Apartment in Sarjapur?",
        filters=PropertyFilters(location="Sarjapur"),
        user_role="buyer",
        vector_store=store,
    )

    assert len(results) == 1
    assert set(results[0].keys()) == {"property_id", "location", "property_type", "price"}
    assert results[0]["price"] == {"quoted_price": 12600000}
    assert "summary" not in results[0]
    assert "highlights" not in results[0]
    assert "visible_price" not in results[0]


def test_location_is_inferred_from_query_when_missing_in_filters():
    fake_doc = Document(
        page_content="Apartment in Whitefield with metro access.",
        metadata={
            "property_id": "P-404",
            "location": "Whitefield, Bangalore",
            "actual_price": 10000000,
            "quoted_price": 10400000,
            "bedrooms": 2,
            "property_type": "Apartment",
            "amenities": ["gym"],
            "sensitive_tags": ["actual_price"],
        },
    )
    store = FakeVectorStore([(fake_doc, 0.93)])

    _ = property_retrieval_tool(
        query="What is the price of Apartment in Whitefield?",
        filters=PropertyFilters(),
        user_role="buyer",
        vector_store=store,
    )

    assert store.last_filter == {"location": "Whitefield, Bangalore"}


def test_results_are_post_filtered_by_inferred_location():
    whitefield_doc = Document(
        page_content="Apartment in Whitefield.",
        metadata={
            "property_id": "P-W",
            "location": "Whitefield, Bangalore",
            "actual_price": 10000000,
            "quoted_price": 10500000,
            "bedrooms": 2,
            "property_type": "Apartment",
            "amenities": ["gym"],
            "sensitive_tags": ["actual_price"],
        },
    )
    other_doc = Document(
        page_content="Apartment in Bellandur.",
        metadata={
            "property_id": "P-B",
            "location": "Bellandur, Bangalore",
            "actual_price": 9000000,
            "quoted_price": 9300000,
            "bedrooms": 2,
            "property_type": "Apartment",
            "amenities": ["parking"],
            "sensitive_tags": ["actual_price"],
        },
    )
    store = FakeVectorStore([(whitefield_doc, 0.9), (other_doc, 0.89)])

    results = property_retrieval_tool(
        query="What is the price of Apartment in Whitefield?",
        filters=PropertyFilters(),
        user_role="buyer",
        vector_store=store,
    )

    assert len(results) == 1
    assert results[0]["property_id"] == "P-W"


def test_whitefiled_typo_is_inferred_as_whitefield():
    whitefield_doc = Document(
        page_content="Apartment in Whitefield.",
        metadata={
            "property_id": "P-W2",
            "location": "Whitefield, Bangalore",
            "actual_price": 10000000,
            "quoted_price": 10500000,
            "bedrooms": 2,
            "property_type": "Apartment",
            "amenities": ["gym"],
            "sensitive_tags": ["actual_price"],
        },
    )
    other_doc = Document(
        page_content="Apartment in Bellandur.",
        metadata={
            "property_id": "P-B2",
            "location": "Bellandur, Bangalore",
            "actual_price": 9000000,
            "quoted_price": 9300000,
            "bedrooms": 2,
            "property_type": "Apartment",
            "amenities": ["parking"],
            "sensitive_tags": ["actual_price"],
        },
    )
    store = FakeVectorStore([(whitefield_doc, 0.9), (other_doc, 0.89)])

    results = property_retrieval_tool(
        query="What is the price of Apartment in Whitefiled?",
        filters=PropertyFilters(),
        user_role="buyer",
        vector_store=store,
    )

    assert len(results) == 1
    assert results[0]["property_id"] == "P-W2"


def test_malformed_role_rejected():
    data = [{"property_id": "P1", "location": "Whitefield, Bangalore", "quoted_price": 110}]
    try:
        apply_role_based_filter(data, user_role="superuser")
    except ValueError as exc:
        assert "Unsupported role" in str(exc)
    else:
        raise AssertionError("Malformed role should be rejected")


def test_missing_role_rejected():
    data = [{"property_id": "P1", "location": "Whitefield, Bangalore", "quoted_price": 110}]
    try:
        apply_role_based_filter(data, user_role=None)
    except ValueError as exc:
        assert "required" in str(exc)
    else:
        raise AssertionError("Missing role should be rejected")
