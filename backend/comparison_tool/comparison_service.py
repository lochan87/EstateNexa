from __future__ import annotations

import re
from typing import Any, Optional

from langchain_core.documents import Document

try:
    from .access_control import filter_documents_for_role
    from .config import get_settings
    from .ingestion import ingest_documents
    from .vector_store import collection_document_count, get_vector_store
except ImportError:
    from access_control import filter_documents_for_role
    from config import get_settings
    from ingestion import ingest_documents
    from vector_store import collection_document_count, get_vector_store


class ComparisonService:
    def __init__(self, groq_api_key: str | None = None) -> None:
        self.settings = get_settings()
        self.vector_store = get_vector_store()
        self.groq_api_key = groq_api_key or self.settings.groq_api_key

        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise ImportError(
                "langchain_groq is required for the comparison tool. Install it with 'pip install langchain-groq'."
            ) from exc

        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is required to run the comparison tool.")

        self.llm = ChatGroq(
            temperature=0,
            groq_api_key=self.groq_api_key,
            model_name="mixtral-8x7b-32768",
            max_tokens=500,
            request_timeout=15,
        )

    def ensure_ingested(self) -> dict[str, int] | None:
        if collection_document_count() > 0:
            return None
        return ingest_documents()

    def extract_locations(self, query: str) -> list[str]:
        lowered = re.sub(r"\s+", " ", query.lower()).strip()
        found: list[str] = []

        aliases = {
            "whitefield": "Whitefield",
            "electronic city": "Electronic City",
            "sarjapur": "Sarjapur",
            "marathahalli": "Marathahalli",
            "yelahanka": "Yelahanka",
            "hebbal": "Hebbal",
            "hsr layout": "HSR Layout",
            "bellandur": "Bellandur",
            "kr puram": "KR Puram",
            "bannerghatta": "Bannerghatta",
        }

        for alias, canonical in aliases.items():
            if alias in lowered and canonical not in found:
                found.append(canonical)

        return found

    def _retrieve_by_source(self, query: str, source: str, top_k: int) -> list[Document]:
        return self.vector_store.similarity_search(
            query=query,
            k=top_k,
            filter={"source": source},
        )

    def _limit_to_locations(self, documents: list[Document], locations: list[str]) -> list[Document]:
        if not locations:
            return documents
        allowed = {location.lower() for location in locations}
        return [doc for doc in documents if str((doc.metadata or {}).get("area", "")).lower() in allowed]

    def _build_prompt(
        self,
        query: str,
        user_role: str,
        visible_context: list[dict[str, Any]],
        locations: list[str],
    ) -> str:
        context_blocks = []
        for item in visible_context:
            label = f"{item['source']} | {item.get('area', 'Unknown Area')}"
            context_blocks.append(f"[{label}]\n{item['content']}")

        context_text = "\n\n".join(context_blocks) if context_blocks else "No accessible comparison data was found."
        location_text = ", ".join(locations) if locations else "No explicit locations detected"

        return f"""
You are a real-estate comparison assistant.

User role: {user_role}
Detected locations: {location_text}

Security rules:
- Use only the provided context.
- Never infer or reconstruct hidden or restricted data.
- If information is restricted or missing, say exactly: "This information is not available for your access level."
- Do not mention actual prices for buyers.
- Do not mention agent identity or contact details for buyers.
- Keep the answer structured and comparison-focused.

Required output sections:
1. Locations Compared
2. Property Comparison
3. Market Trends
4. Growth Potential
5. Strengths and Risks
6. Final Recommendation

Inside Property Comparison include:
- price comparison
- size
- amenities

Inside Final Recommendation include:
- best for investment
- best for affordability

User query:
{query}

Accessible context:
{context_text}
""".strip()

    def _format_property_line(self, item: dict[str, Any], user_role: str) -> str:
        metadata = item.get("metadata", {})
        area = item.get("area") or metadata.get("area") or "Unknown"
        property_id = metadata.get("property_id") or "Unknown"
        quoted_price = metadata.get("quoted_price") or "This information is not available for your access level."
        size_sq_ft = metadata.get("size_sq_ft") or "N/A"
        bedrooms = metadata.get("bedrooms") or "N/A"
        amenities = metadata.get("amenities") or "N/A"

        lines = [
            f"- {area} | Property {property_id}",
            f"  Quoted price: {quoted_price}",
            f"  Size: {size_sq_ft} sq ft",
            f"  Bedrooms: {bedrooms}",
            f"  Amenities: {amenities}",
        ]

        if user_role in {"agent", "admin"}:
            actual_price = metadata.get("actual_price") or "N/A"
            lines.append(f"  Actual price: {actual_price}")

        return "\n".join(lines)

    def _extract_location_metrics(self, content: str) -> dict[str, str]:
        def find(pattern: str) -> str:
            match = re.search(pattern, content, flags=re.IGNORECASE | re.DOTALL)
            return re.sub(r"\s+", " ", match.group(1)).strip() if match else "Not clearly available"

        return {
            "buy_price_range": find(r"Buy Price Range\s+(.+?)(?:Rental Trends|Investment Potential)"),
            "rental_trends": find(r"Rental Trends\s+(.+?)(?:Investment Potential|Short-term Outlook)"),
            "investment_potential": find(r"Investment Potential\s+(.+?)(?:Short-term Outlook|Long-term Outlook)"),
            "short_term_outlook": find(r"Short-term Outlook\s+(.+?)(?:Long-term Outlook|11\. PROS AND CONS)"),
            "long_term_outlook": find(r"Long-term Outlook\s+(.+?)(?:11\. PROS AND CONS|Advantages:)"),
            "advantages": find(r"Advantages:\s+(.+?)(?:Drawbacks:)"),
            "drawbacks": find(r"Drawbacks:\s+(.+?)(?:Bangalore Location Intelligence Report|$)"),
        }

    def _build_fallback_answer(
        self,
        query: str,
        user_role: str,
        visible_context: list[dict[str, Any]],
        locations: list[str],
        failure_reason: str,
    ) -> str:
        property_items = [item for item in visible_context if item.get("source") == "property_listing"]
        location_items = [item for item in visible_context if item.get("source") == "location"]

        price_map: dict[str, float] = {}
        for item in property_items:
            metadata = item.get("metadata", {})
            raw_price = str(metadata.get("quoted_price", "")).replace(",", "")
            digits = re.sub(r"[^0-9.]", "", raw_price)
            if digits:
                price_map[item.get("area") or "Unknown"] = float(digits)

        investment_scores: dict[str, int] = {}
        for item in location_items:
            metrics = self._extract_location_metrics(item.get("content", ""))
            score = 0
            if "high" in metrics["investment_potential"].lower():
                score += 2
            if "strong" in metrics["long_term_outlook"].lower():
                score += 2
            if "high" in metrics["rental_trends"].lower() or "5 to 6 percent" in metrics["rental_trends"].lower():
                score += 1
            investment_scores[item.get("area") or "Unknown"] = score

        best_for_investment = max(investment_scores, key=investment_scores.get) if investment_scores else "Not enough data"
        best_for_affordability = min(price_map, key=price_map.get) if price_map else "Not enough data"

        property_section = "\n".join(
            self._format_property_line(item, user_role=user_role) for item in property_items
        ) or "No accessible property data found."

        market_lines = []
        strength_lines = []
        for item in location_items:
            area = item.get("area") or "Unknown"
            metrics = self._extract_location_metrics(item.get("content", ""))
            market_lines.append(
                "\n".join(
                    [
                        f"- {area}",
                        f"  Buy price range: {metrics['buy_price_range']}",
                        f"  Rental trends: {metrics['rental_trends']}",
                        f"  Investment potential: {metrics['investment_potential']}",
                        f"  Growth outlook: {metrics['short_term_outlook']} | {metrics['long_term_outlook']}",
                    ]
                )
            )
            strength_lines.append(
                "\n".join(
                    [
                        f"- {area}",
                        f"  Strengths: {metrics['advantages']}",
                        f"  Risks: {metrics['drawbacks']}",
                    ]
                )
            )

        locations_text = ", ".join(locations) if locations else "No explicit locations detected"

        return (
            f"1. Locations Compared\n"
            f"{locations_text}\n\n"
            f"2. Property Comparison\n"
            f"{property_section}\n\n"
            f"3. Market Trends\n"
            f"{chr(10).join(market_lines) or 'No accessible market trend data found.'}\n\n"
            f"4. Growth Potential\n"
            f"Comparison is based on the retrieved location outlook and investment indicators for the query: {query}\n\n"
            f"5. Strengths and Risks\n"
            f"{chr(10).join(strength_lines) or 'No accessible strengths and risks data found.'}\n\n"
            f"6. Final Recommendation\n"
            f"Best for investment: {best_for_investment}\n"
            f"Best for affordability: {best_for_affordability}\n"
            f"Note: LLM fallback mode was used because external generation failed: {failure_reason}"
        )

    def _store_ai_response(self, query: str, response: str) -> dict[str, Any]:
        try:
            import psycopg2
        except ImportError as exc:
            return {
                "saved": False,
                "error": "psycopg2 is required to store ai_responses entries.",
                "details": str(exc),
            }

        try:
            conn = psycopg2.connect(
                host=self.settings.db_host,
                port=self.settings.db_port,
                dbname=self.settings.db_name,
                user=self.settings.db_user,
                password=self.settings.db_password,
            )
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO ai_responses (session_id, user_id, query, response, tool_used)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (None, None, query, response, "comparison_tool"),
            )
            conn.commit()
            cur.close()
            conn.close()
            return {"saved": True, "error": None}
        except Exception as exc:
            return {"saved": False, "error": str(exc)}

    def compare(
        self,
        query: str,
        user_role: str,
        user_agent_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if collection_document_count() == 0:
            raise ValueError("Comparison data is not ingested yet. Run /comparison/ingest first.")

        ingestion_result = None
        locations = self.extract_locations(query)

        property_docs = self._retrieve_by_source(query=query, source="property_listing", top_k=10)
        location_docs = self._retrieve_by_source(query=query, source="location", top_k=10)

        property_docs = self._limit_to_locations(property_docs, locations)
        location_docs = self._limit_to_locations(location_docs, locations)

        visible_context = filter_documents_for_role(
            documents=[*property_docs, *location_docs],
            user_role=user_role,
            user_agent_id=user_agent_id,
        )

        prompt = self._build_prompt(
            query=query,
            user_role=user_role,
            visible_context=visible_context,
            locations=locations,
        )
        generation_mode = "groq"
        try:
            llm_response = self.llm.invoke(prompt)
            answer = getattr(llm_response, "content", str(llm_response))
        except Exception as exc:
            generation_mode = "fallback"
            answer = self._build_fallback_answer(
                query=query,
                user_role=user_role,
                visible_context=visible_context,
                locations=locations,
                failure_reason=f"{type(exc).__name__}: {exc}",
            )
        storage_result = self._store_ai_response(query=query, response=answer)

        return {
            "query": query,
            "user_role": user_role,
            "user_agent_id": user_agent_id,
            "generation_mode": generation_mode,
            "detected_locations": locations,
            "property_matches": [
                {
                    "property_id": item["metadata"].get("property_id"),
                    "area": item.get("area"),
                    "source": item.get("source"),
                }
                for item in visible_context
                if item.get("source") == "property_listing"
            ],
            "location_matches": [
                item.get("area")
                for item in visible_context
                if item.get("source") == "location"
            ],
            "answer": answer,
            "storage": storage_result,
            "ingestion": ingestion_result,
        }
