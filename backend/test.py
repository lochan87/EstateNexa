import chromadb

client = chromadb.PersistentClient(path="data/chroma_db")

collections = client.list_collections()
print("Collections:", collections)

collection = client.get_collection("estatenexa_documents")

results = collection.get()

print("\n📄 Documents:")
print(results["documents"][:3])

print("\n🧾 Metadatas:")
print(results["metadatas"][:3])