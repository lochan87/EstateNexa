from typing import Any

from rag.langchain_tools import property_retrieval_structured_tool


def get_agent_tools():
    """Return tools that can be registered in a LangChain agent."""
    return [property_retrieval_structured_tool]


def build_property_tool_payload(query: str, user_role: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build payload so the caller always sends authenticated role to the tool."""
    return {
        "query": query,
        "filters": filters or {},
        "user_role": user_role,
    }
