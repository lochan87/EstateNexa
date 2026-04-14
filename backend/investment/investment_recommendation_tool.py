"""
Investment Recommendation Tool - Full Context Synthesis

Analyzes user queries against full investment insights PDF context using ChromaDB.
Maps insights to property listings and computes best area based on ROI + yield + risk.
Returns natural responses with recommendations.
"""

import os
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from chroma_store import get_chroma_store


def _safe_float(value: any) -> float:
    """Safely convert value to float."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r'[-+]?\d*\.?\d+', value)
        if match:
            return float(match.group())
    return 0.0


class InvestmentRecommendationTool:
    """
    Provides context-aware investment recommendations reading full insights PDF.
    Maps insights to specific properties from listings, identifies best area for ROI.
    """

    def __init__(self):
        """Initialize with Groq LLM for intent + synthesis"""
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        self._chroma_persist_directory = Path(__file__).resolve().parents[1] / "data" / "chroma_db"

        self.llm = ChatGroq(
            temperature=0.1,
            groq_api_key=groq_api_key,
            model_name="mixtral-8x7b-32768",
            max_tokens=1200,
            request_timeout=60,
        )

    def analyze_opportunity(
        self,
        user_query: str,
        investment_insights_text: str,
        property_listings_text: str,
        user_role: str = "buyer",
    ) -> Dict[str, Any]:
        """
        Full analysis: intent → match → synthesize natural response w/ best area + properties.
        """
        try:
            # Load structured data
            insights_data = self._extract_json_from_text(investment_insights_text, "investment_insights")
            property_data = self._extract_json_from_text(property_listings_text, "property_listings")
            market_data = self._extract_json_from_text(investment_insights_text, "market_analysis")
            if self._is_non_investment_query(user_query):
                return {
                    "query": user_query,
                    "best_area": {
                        "location": "N/A",
                        "score": 0.0,
                        "roi": 0.0,
                        "rental_yield": 0.0,
                        "risk_level": "N/A",
                        "property_count": 0,
                        "reasoning": "No investment intent detected in query.",
                    },
                    "synthesized_analysis": "Hi! I can help with property investment decisions. Ask something like 'best area for ROI under 1 crore' or 'Bellandur investment with coordinates'.",
                    "properties_by_area": {},
                    "matched_insights_count": 0,
                    "supporting_chunks": [],
                    "user_role": user_role,
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                }
            
            # Extract intent
            user_intent = self._extract_query_intent(user_query)
            budget_limit = self._extract_budget_limit(user_query)
            mentioned_locations = self._extract_locations_from_query(
                user_query,
                insights_data,
                market_data,
                property_data,
            )
            forced_location = self._select_forced_location(user_query, mentioned_locations)
            
            # Match top 8 insights
            matched_insights = self._match_insights(user_query, user_intent, insights_data)[:8]
            
            # Chroma chunks for additional context
            supporting_chunks = self._get_relevant_chunks(user_query, user_role)
            
            # Match properties per insight area
            properties_by_area = self._match_properties_per_area(
                matched_insights,
                property_data,
                user_role=user_role,
                market_data=market_data,
                user_query=user_query,
                budget_limit=budget_limit,
            )
            
            # Compute best area
            best_area = self._compute_best_area(
                matched_insights,
                properties_by_area,
                market_data=market_data,
                user_query=user_query,
                budget_limit=budget_limit,
                mentioned_locations=mentioned_locations,
                forced_location=forced_location,
            )
            
            # Synthesize full natural response using ALL context
            synthesized_analysis = self._synthesize_full_analysis(
                query=user_query,
                insights=matched_insights,
                properties_by_area=properties_by_area,
                best_area=best_area,
                chunks=supporting_chunks,
                user_role=user_role,
                market_data=market_data,
                mentioned_locations=mentioned_locations,
                budget_limit=budget_limit,
            )
            
            response = {
                "query": user_query,
                "best_area": best_area,
                "synthesized_analysis": synthesized_analysis,
                "properties_by_area": properties_by_area,
                "matched_insights_count": len(matched_insights),
                "supporting_chunks": supporting_chunks,
                "user_role": user_role,
                "analysis_timestamp": datetime.utcnow().isoformat(),
            }
            
            return response
            
        except Exception as e:
            print(f"Analysis error: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_response("Bangalore", str(e))

    def _get_relevant_chunks(self, query: str, user_role: str) -> List[Dict]:
        """Get relevant Chroma chunks from full investment insights PDF."""
        try:
            vector_store = get_chroma_store(persist_directory=str(self._chroma_persist_directory))
            results = []
            results.extend(vector_store.search_documents(query, top_k=10, filters={"source": "Investment_Insights.pdf"}))
            results.extend(vector_store.search_documents(query, top_k=10, filters={"source": "Market_Analysis_ Report.pdf"}))
            if not results:
                results = vector_store.search_documents(query, top_k=15)
            allowed_doc_roles = {
                "admin": {"admin", "agent", "buyer"},
                "agent": {"agent", "buyer"},
                "buyer": {"buyer"},
            }.get(user_role, {"buyer"})
            
            seen = set()
            chunks = []
            for r in results:
                content = r.get("content", "").strip()
                metadata = r.get("metadata", {}) or {}
                doc_access_role = metadata.get("access_role")
                if doc_access_role and doc_access_role not in allowed_doc_roles:
                    continue
                if content and content not in seen:
                    chunks.append({"content": content, "score": r.get("score", 0)})
                    seen.add(content)
            return chunks
        except:
            return []

    def _match_properties_per_area(
        self,
        insights: List[Dict],
        properties: List[Dict],
        user_role: str,
        market_data: Optional[List[Dict]] = None,
        user_query: str = "",
        budget_limit: Optional[float] = None,
    ) -> Dict[str, List[Dict]]:
        """Map properties to insight locations (ROI-focused)."""
        area_props = {}
        locations_map = {}
        
        for insight in insights:
            if insight.get("insight_type") == "Location":
                loc_lower = (insight.get("target_category", "") or "").lower()
                if loc_lower:
                    locations_map[loc_lower] = insight.get("target_category", "")
        for market in market_data or []:
            mloc = (market.get("location") or "").strip()
            if mloc:
                locations_map[self._normalize_location(mloc)] = mloc
        for qloc in self._extract_locations_from_query(user_query, insights, market_data or [], properties):
            locations_map[self._normalize_location(qloc)] = qloc
        
        for prop in properties:
            prop_loc = self._normalize_location(prop.get("location") or "")
            for loc_lower, loc_proper in locations_map.items():
                if not loc_lower:
                    continue
                if loc_lower in prop_loc or prop_loc in loc_lower:
                    if loc_proper not in area_props:
                        area_props[loc_proper] = []
                    quoted_price = (
                        prop.get("quoted_price_inr")
                        or prop.get("quoted_price")
                        or prop.get("listed_price")
                        or prop.get("price")
                    )
                    actual_price = (
                        prop.get("actual_price_inr")
                        or prop.get("actual_price")
                    )
                    property_entry = {
                        "property_id": prop.get("property_id") or prop.get("id"),
                        "title": (
                            prop.get("title")
                            or prop.get("name")
                            or f"{(prop.get('property_type') or prop.get('type') or 'Property')} in {prop.get('location') or 'Bangalore'}"
                        ),
                        "location": prop.get("location"),
                        "bedrooms": prop.get("bedrooms") or prop.get("beds"),
                        "property_type": prop.get("property_type") or prop.get("type"),
                        "agent_id": prop.get("agent_id"),
                        "coordinates": prop.get("coordinates"),
                    }
                    if user_role in {"admin", "agent"}:
                        property_entry["actual_price"] = actual_price
                        property_entry["quoted_price"] = quoted_price
                        property_entry["price"] = quoted_price or actual_price
                    else:
                        property_entry["quoted_price"] = quoted_price
                        property_entry["price"] = quoted_price
                    area_props[loc_proper].append({
                        **property_entry
                    })
                    break
        if budget_limit and budget_limit > 0:
            for area, props in list(area_props.items()):
                affordable = [p for p in props if _safe_float(p.get("quoted_price", p.get("price"))) <= budget_limit]
                if affordable:
                    area_props[area] = affordable
        return area_props

    def _compute_best_area(
        self,
        insights: List[Dict],
        properties_by_area: Dict,
        market_data: Optional[List[Dict]] = None,
        user_query: str = "",
        budget_limit: Optional[float] = None,
        mentioned_locations: Optional[List[str]] = None,
        forced_location: Optional[str] = None,
    ) -> Dict:
        """Compute best area with blended insight + market + budget aware scoring."""
        area_scores = {}
        market_data = market_data or []
        mentioned_locations = mentioned_locations or []

        location_insights = [x for x in insights if x.get("insight_type") == "Location"]
        candidate_map: Dict[str, str] = {}

        def add_candidate(area_name: str) -> None:
            norm = self._normalize_location(area_name or "")
            if not norm:
                return
            if norm not in candidate_map:
                candidate_map[norm] = area_name

        for area_name in properties_by_area.keys():
            add_candidate(area_name)
        for row in location_insights:
            add_candidate(row.get("target_category", ""))
        for row in market_data:
            add_candidate(row.get("location", ""))
        for area_name in mentioned_locations:
            add_candidate(area_name)

        for area in candidate_map.values():
            if not area:
                continue
            insight = self._find_matching_location_entry(location_insights, "target_category", area)
            market = self._find_matching_location_entry(market_data, "location", area)

            market_growth = _safe_float((market or {}).get("price_growth_percent", 0))
            roi = _safe_float((insight or {}).get("expected_capital_appreciation_max", 0)) or market_growth
            yield_ = _safe_float((insight or {}).get("expected_rental_yield_max", 0))
            if yield_ <= 0:
                rental_demand = ((market or {}).get("rental_demand", "Medium") or "Medium").lower()
                yield_ = {"high": 5.0, "medium": 3.8, "low": 2.8}.get(rental_demand, 3.8)

            risk_level = (insight or {}).get("risk_level")
            if not risk_level:
                risk_items = (market or {}).get("risks", []) or []
                risk_level = "Low" if len(risk_items) <= 1 else "Medium" if len(risk_items) <= 2 else "High"
            risk = {"Low": 0, "Medium": 1, "High": 2}.get(risk_level, 1)

            props = self._get_area_properties(properties_by_area, area)
            prop_count = len(props)
            affordable_count = 0
            if budget_limit and budget_limit > 0:
                affordable_count = sum(
                    1 for p in props if _safe_float(p.get("quoted_price", p.get("price"))) <= budget_limit
                )
            budget_bonus = 0.0
            if budget_limit and budget_limit > 0:
                budget_bonus = (affordable_count / max(prop_count, 1)) * 2.0 if prop_count else -0.5

            mention_boost = 2.5 if any(self._normalize_location(m) == self._normalize_location(area) for m in mentioned_locations) else 0.0
            force_boost = 10.0 if forced_location and self._normalize_location(forced_location) == self._normalize_location(area) else 0.0
            rental_demand_bonus = {"high": 1.0, "medium": 0.5, "low": 0.0}.get(
                ((market or {}).get("rental_demand", "Medium") or "Medium").lower(),
                0.5,
            )

            score = (
                roi * 0.55
                + yield_ * 0.2
                + market_growth * 0.2
                + rental_demand_bonus
                + prop_count * 0.2
                + budget_bonus
                + mention_boost
                + force_boost
                - risk * 0.6
            )

            reasoning_parts = []
            if (insight or {}).get("reasoning"):
                reasoning_parts.append((insight or {}).get("reasoning"))
            if (market or {}).get("assessment"):
                reasoning_parts.append((market or {}).get("assessment"))

            area_scores[area] = {
                "roi": round(roi, 2),
                "rental_yield": round(yield_, 2),
                "risk_level": risk_level,
                "property_count": prop_count,
                "score": round(score, 2),
                "reasoning": " ".join(reasoning_parts).strip() or "Balanced score from market growth, yield, risk, and listing availability.",
            }
        
        if not area_scores:
            return {"location": "Bangalore", "score": 0, "roi": 0, "rental_yield": 0, "risk_level": "Medium", "property_count": 0, "reasoning": "Fallback"}
        
        best = max(area_scores.items(), key=lambda x: x[1]["score"])
        best_location, best_metrics = best
        return {
            "location": best_location,
            **best_metrics,
        }

    def _synthesize_full_analysis(
        self,
        query: str,
        insights: List,
        properties_by_area: Dict,
        best_area: Dict,
        chunks: List,
        user_role: str,
        market_data: Optional[List[Dict]] = None,
        mentioned_locations: Optional[List[str]] = None,
        budget_limit: Optional[float] = None,
    ) -> str:
        """LLM synthesis: Natural response from full context."""
        market_data = market_data or []
        mentioned_locations = mentioned_locations or []
        # Build properties excerpt
        props_excerpt = ""
        for area, props in list(properties_by_area.items())[:3]:
            props_excerpt += f"\n{area}:\n"
            for p in props[:2]:
                if user_role in {"admin", "agent"}:
                    props_excerpt += (
                        f"  - {p.get('title')}: Quoted Rs {p.get('quoted_price')} | "
                        f"Actual Rs {p.get('actual_price')} ({p.get('bedrooms')} BHK)\n"
                    )
                else:
                    props_excerpt += (
                        f"  - {p.get('title')}: Quoted Rs {p.get('quoted_price')} "
                        f"({p.get('bedrooms')} BHK)\n"
                    )
                if p.get("coordinates"):
                    lat = p.get("coordinates", {}).get("latitude")
                    lng = p.get("coordinates", {}).get("longitude")
                    if lat and lng:
                        props_excerpt += f"    Coordinates: ({lat}, {lng})\n"
        market_excerpt = json.dumps(
            [
                {
                    "location": m.get("location"),
                    "rental_demand": m.get("rental_demand"),
                    "price_growth_percent": m.get("price_growth_percent"),
                    "assessment": m.get("assessment"),
                }
                for m in market_data
            ],
            indent=2,
        )
        
        prompt = f"""You are a senior real estate investment advisor. Answer the user's investment query naturally using the full context below.

User Query: {query}

MATCHED INSIGHTS (from Investment_Insights.pdf):
{json.dumps([{"location": i.get("target_category"), "roi": i.get("expected_capital_appreciation_max"), "yield": i.get("expected_rental_yield_max"), "risk": i.get("risk_level"), "recommendation": i.get("recommendation"), "reasoning": i.get("reasoning")} for i in insights[:5]], indent=2)}

BEST AREA (computed): {best_area.get('location')} - ROI: {best_area.get('roi')}%, Yield: {best_area.get('rental_yield')}%

AVAILABLE PROPERTIES BY AREA:{props_excerpt}

MARKET ANALYSIS LOCATIONS:
{market_excerpt}

USER CONTEXT:
- Mentioned locations: {mentioned_locations}
- Budget cap (if any): {budget_limit if budget_limit else "Not specified"}

SUPPORTING CHUNKS (from PDF):
{chr(10).join([c['content'][:120] + '...' for c in chunks[:2]])}

Response Guidelines:
1. Answer the user's query directly (e.g., "Best area to invest: [AREA] because...")
2. Mention ROI%, rental yield, and risk level
3. Explain the reasoning in 2-3 lines using market signals (demand, infrastructure, growth corridor, tenant demand)
4. List 2-3 SPECIFIC PROPERTIES with location, price, type, bedrooms
4. If user role is buyer: show ONLY quoted price. If admin/agent: show quoted and actual price.
5. Briefly mention 1-2 other good areas and why they are secondary
6. End with next steps (viewing, financing options, negotiation strategy)
7. Be concise, conversational, and authoritative - like a real estate advisor
8. If user asks for a specific location, answer that location directly first before comparing alternatives.
9. If user asks for coordinates or nearby options, include coordinates for matched properties when available.

RESPOND NOW:"""

        try:
            print(
                f"[investment_tool] LLM call (synthesis) | query_len={len(query)} "
                f"| insights={len(insights)} | chunk_count={len(chunks)}"
            )
            response = self.llm.invoke([HumanMessage(content=prompt)])
            response_text = str(getattr(response, "content", "") or "").strip()
            print(f"[investment_tool] LLM response (synthesis) | chars={len(response_text)}")
            if response_text:
                return response_text
            return self._build_structured_fallback_analysis(
                query, insights, properties_by_area, best_area, user_role, market_data, mentioned_locations
            )
        except Exception as e:
            print(f"LLM synthesis error: {e}")
            return self._build_structured_fallback_analysis(
                query, insights, properties_by_area, best_area, user_role, market_data, mentioned_locations
            )

    def _build_structured_fallback_analysis(
        self,
        query: str,
        insights: List[Dict],
        properties_by_area: Dict[str, List[Dict]],
        best_area: Dict[str, Any],
        user_role: str,
        market_data: Optional[List[Dict]] = None,
        mentioned_locations: Optional[List[str]] = None,
    ) -> str:
        """Deterministic advisor-style fallback when LLM output fails."""
        best_location = best_area.get("location", "Bangalore")
        best_props = properties_by_area.get(best_location, [])[:3]
        best_reason = best_area.get("reasoning") or "Strong ROI potential with balanced risk profile."

        alternatives = []
        seen_alt_norm = set()
        for item in insights:
            alt_loc = item.get("target_category")
            alt_norm = self._normalize_location(alt_loc or "")
            best_norm = self._normalize_location(best_location)
            if (
                item.get("insight_type") == "Location"
                and alt_loc
                and alt_norm
                and alt_norm != best_norm
                and alt_norm not in seen_alt_norm
            ):
                alternatives.append(alt_loc)
                seen_alt_norm.add(alt_norm)
            if len(alternatives) >= 2:
                break

        lines = [
            f"Best area to invest for ROI: {best_location}.",
            f"It stands out with an estimated ROI of {best_area.get('roi', 0)}% and rental yield of {best_area.get('rental_yield', 0)}%, with {best_area.get('risk_level', 'Medium')} risk.",
            f"Reasoning: {best_reason}",
            "",
            "Recommended properties:",
        ]

        if best_props:
            for prop in best_props:
                title = prop.get("title", "Property")
                ptype = prop.get("property_type", "N/A")
                beds = prop.get("bedrooms")
                bed_label = "N/A" if beds in [None, 0, "0"] else str(beds)
                quoted = prop.get("quoted_price", prop.get("price", "N/A"))
                actual = prop.get("actual_price")
                if user_role in {"admin", "agent"} and actual is not None:
                    lines.append(f"- {title} ({ptype}, {bed_label} BHK): Quoted Rs {quoted}, Actual Rs {actual}")
                else:
                    lines.append(f"- {title} ({ptype}, {bed_label} BHK): Quoted Rs {quoted}")
                if prop.get("coordinates"):
                    lat = prop.get("coordinates", {}).get("latitude")
                    lng = prop.get("coordinates", {}).get("longitude")
                    if lat and lng:
                        lines.append(f"  Coordinates: ({lat}, {lng})")
        else:
            lines.append("- No direct listing match found in this area yet.")

        requested = mentioned_locations or []
        if requested:
            lines.append("")
            lines.append(f"Requested area focus: {', '.join(requested)}")
            for loc in requested[:2]:
                loc_props = properties_by_area.get(loc, [])[:2]
                if not loc_props:
                    continue
                lines.append(f"- {loc}:")
                for prop in loc_props:
                    title = prop.get("title", "Property")
                    quoted = prop.get("quoted_price", prop.get("price", "N/A"))
                    coord = prop.get("coordinates") or {}
                    coord_text = ""
                    if coord.get("latitude") and coord.get("longitude"):
                        coord_text = f", Coordinates: ({coord.get('latitude')}, {coord.get('longitude')})"
                    lines.append(f"  {title} - Quoted Rs {quoted}{coord_text}")

        if alternatives:
            lines.append("")
            lines.append("Other good areas to consider:")
            for alt in alternatives:
                lines.append(f"- {alt}")

        lines.append("")
        lines.append("Next steps: shortlist 2 properties, schedule site visits, and compare rental demand before final negotiation.")
        return "\n".join(lines)

    def _extract_json_from_text(self, text: str, key: str) -> List[Dict]:
        """Load structured investment and property data from pre-extracted JSON file."""
        try:
            json_file_path = Path(__file__).parent / "PDF_EXTRACTION_STRUCTURED_DATA.json"
            if json_file_path.exists():
                with open(json_file_path, 'r') as f:
                    data = json.load(f)
                if key in data:
                    result = data[key]
                    return result if isinstance(result, list) else [result]
            return []
        except Exception as e:
            print(f"Error loading structured data: {str(e)}")
            return []

    def _extract_query_intent(self, query: str) -> Dict[str, Any]:
        """Use LLM to extract intent from query"""
        prompt = f"""Analyze this investment query and extract intent:

Query: {query}

Return ONLY JSON:
{{
  "investment_type": "rental" or "resale" or "both",
  "risk_appetite": "low" or "medium" or "high",
  "budget_mentioned": true/false,
  "location_mentioned": true/false,
  "property_type": "apartment" or "villa" or "plot" or "any",
  "time_horizon": "short" or "medium" or "long"
}}"""

        try:
            print(f"[investment_tool] LLM call (intent) | query_len={len(query)}")
            response = self.llm.invoke([HumanMessage(content=prompt)])
            response_text = str(getattr(response, "content", "") or "")
            print(f"[investment_tool] LLM response (intent) | chars={len(response_text)}")
            cleaned = re.sub(r"^```(?:json)?|```$", "", response_text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
            json_match = re.search(r'\{.*?\}', cleaned, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        return {
            "investment_type": "both",
            "risk_appetite": "medium",
            "budget_mentioned": False,
            "location_mentioned": False,
            "property_type": "any",
            "time_horizon": "medium"
        }

    def _extract_budget_limit(self, query: str) -> Optional[float]:
        """Parse budget mentions from query and return max budget in INR."""
        q = (query or "").lower()
        crore_match = re.search(r"(\d+(?:\.\d+)?)\s*crore", q)
        if crore_match:
            return float(crore_match.group(1)) * 10000000
        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*lakh", q)
        if lakh_match:
            return float(lakh_match.group(1)) * 100000
        cr_short_match = re.search(r"(\d+(?:\.\d+)?)\s*cr\b", q)
        if cr_short_match:
            return float(cr_short_match.group(1)) * 10000000
        amount_match = re.search(r"(?:under|below|within|budget)\s*₹?\s*(\d+(?:\.\d+)?)\s*(?:k|m)?", q)
        if amount_match:
            raw = float(amount_match.group(1))
            if raw < 1000:
                return raw * 100000  # assume lakh-scale casual input
            return raw
        return None

    def _normalize_location(self, value: str) -> str:
        v = (value or "").strip().lower()
        v = v.replace("road", "").replace("-", " ")
        v = re.sub(r"\s+", " ", v).strip()
        return v

    def _extract_locations_from_query(
        self,
        query: str,
        insights: List[Dict],
        market_data: List[Dict],
        properties: List[Dict],
    ) -> List[str]:
        query_norm = self._normalize_location(query)
        candidates = []
        candidates.extend([x.get("target_category") for x in insights if x.get("target_category")])
        candidates.extend([x.get("location") for x in market_data if x.get("location")])
        candidates.extend([x.get("location") for x in properties if x.get("location")])

        seen = set()
        matched = []
        for loc in candidates:
            if not loc:
                continue
            norm = self._normalize_location(loc)
            if norm and norm in query_norm and norm not in seen:
                matched.append(loc)
                seen.add(norm)
        return matched

    def _find_matching_location_entry(self, rows: List[Dict], key: str, location: str) -> Optional[Dict]:
        loc_norm = self._normalize_location(location)
        for row in rows:
            row_norm = self._normalize_location((row or {}).get(key, ""))
            if row_norm == loc_norm or row_norm in loc_norm or loc_norm in row_norm:
                return row
        return None

    def _select_forced_location(self, query: str, mentioned_locations: List[str]) -> Optional[str]:
        """Force focus on a requested location for 'tell me about X'-style queries."""
        if not mentioned_locations:
            return None
        q = (query or "").lower()
        intent_markers = [
            "tell me about",
            "about ",
            "details about",
            "investment in ",
            "properties in ",
            "coordinate",
            "coordinates",
        ]
        ranking_markers = ["best roi", "best area", "highest roi", "top area", "where should i invest"]
        if any(m in q for m in intent_markers) and not any(m in q for m in ranking_markers):
            return mentioned_locations[0]
        return None

    def _get_area_properties(self, properties_by_area: Dict[str, List[Dict]], area: str) -> List[Dict]:
        """Return properties matching area with normalized-name matching."""
        area_norm = self._normalize_location(area)
        for key, props in properties_by_area.items():
            if self._normalize_location(key) == area_norm:
                return props
        return []

    def _is_non_investment_query(self, query: str) -> bool:
        """Detect greeting/small-talk that should not trigger investment analysis."""
        q = (query or "").strip().lower()
        if not q:
            return True
        greetings = {"hi", "hello", "hey", "yo", "hola", "good morning", "good evening", "how are you"}
        if q in greetings:
            return True
        investment_keywords = [
            "invest", "roi", "yield", "rental", "property", "area", "budget", "location",
            "appreciation", "risk", "buy", "sell", "flat", "apartment", "villa", "plot",
            "crore", "lakh", "bangalore", "whitefield", "sarjapur", "yelahanka", "hebbal",
            "bellandur", "electronic city", "hsr", "kr puram", "bannerghatta",
        ]
        return not any(k in q for k in investment_keywords)

    def _match_insights(
        self,
        query: str,
        intent: Dict,
        insights: List[Dict]
    ) -> List[Dict]:
        """Match query against insight conditions and return matching insights"""
        matched = []
        query_lower = query.lower()
        
        for insight in insights:
            condition = (insight.get("condition", "") or "").lower()
            target = (insight.get("target_category", "") or "").lower()
            reasoning = (insight.get("reasoning", "") or "").lower()
            
            score = 0
            
            # Check direct keyword matches
            if "rental" in query_lower and "rental" in condition:
                score += 3
            if "resale" in query_lower and "capital" in condition:
                score += 3
            if "appreciation" in query_lower and "appreciation" in condition:
                score += 3
            if "long-term" in query_lower and "long" in condition:
                score += 2
            if "first" in query_lower and "first" in condition:
                score += 2
            if "budget" in query_lower and "budget" in condition:
                score += 2
            if "high" in query_lower and "high" in condition:
                score += 1
            if "low" in query_lower and "low" in condition:
                score += 1
            if "medium" in query_lower and "medium" in condition:
                score += 1
            
            # Match risk appetite
            if intent.get("risk_appetite") == "low" and insight.get("risk_level") == "Low":
                score += 2
            elif intent.get("risk_appetite") == "high" and insight.get("risk_level") in ["Medium", "High"]:
                score += 2
            elif intent.get("risk_appetite") == "medium":
                score += 1
            
            # Match property type if mentioned
            property_type = (intent.get("property_type", "") or "").lower()
            target_lower = target.lower()
            if property_type != "any" and property_type in target_lower:
                score += 2
            
            if score > 0:
                insight["match_score"] = score
                matched.append(insight)
        
        # Sort by score and return top matches
        matched.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        return matched[:8]

    def _create_fallback_response(self, location: str, error: str = None) -> Dict[str, Any]:
        """Create fallback response with reasonable defaults"""
        return {
            "query": "Unable to process query",
            "best_area": {
                "location": "Whitefield",
                "roi": 10.0,
                "rental_yield": 5.0,
                "risk_level": "Low",
                "property_count": 3,
                "score": 10.0,
                "reasoning": "Fallback: Tech corridor with strong fundamentals"
            },
            "synthesized_analysis": "Unable to complete analysis. Please try again.",
            "properties_by_area": {},
            "matched_insights_count": 0,
            "supporting_chunks": [],
            "user_role": "buyer",
            "analysis_timestamp": datetime.utcnow().isoformat(),
        }


# Initialize tool globally
investment_tool = InvestmentRecommendationTool()
