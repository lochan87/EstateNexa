from langchain_core.tools import StructuredTool

from rag.models import PropertyRetrievalInput
from rag.retrieval import property_retrieval_tool


def _tool_runner(query: str, filters: dict, user_role: str):
    request = PropertyRetrievalInput(query=query, filters=filters, user_role=user_role)
    return property_retrieval_tool(
        query=request.query,
        filters=request.filters,
        user_role=request.user_role,
    )


property_retrieval_structured_tool = StructuredTool.from_function(
    func=_tool_runner,
    name="property_retrieval_tool",
    description=(
        "Retrieve real-estate properties by semantic similarity with strict role-based output filtering. "
        "Always pass authenticated user_role exactly as buyer, agent, or admin. "
        "Use filters for budget, location, bedrooms, and property_type when the user provides constraints."
    ),
)
