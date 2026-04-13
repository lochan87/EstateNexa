import json

try:
    from .comparison_service import ComparisonService
except ImportError:
    from comparison_service import ComparisonService


def main() -> None:
    query = "Compare Whitefield and Electronic City properties for investment"
    role = "buyer"

    service = ComparisonService()
    result = service.compare(query=query, user_role=role, user_agent_id=None)

    print("Detected locations:", result["detected_locations"])
    print("Property matches:", result["property_matches"])
    print("Location matches:", result["location_matches"])
    print("\nStructured comparison:\n")
    print(result["answer"])
    print("\nStorage status:")
    print(json.dumps(result["storage"], indent=2))


if __name__ == "__main__":
    main()
