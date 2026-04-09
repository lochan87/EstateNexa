import argparse

from rag.ingestion import ingest_property_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest property dataset into vector store")
    parser.add_argument("--dataset", required=True, help="Path to CSV, JSON, or PDF property dataset")
    args = parser.parse_args()

    count = ingest_property_dataset(args.dataset)
    print(f"Ingested {count} property documents")


if __name__ == "__main__":
    main()
