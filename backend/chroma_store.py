"""
ChromaDB Vector Database Integration
Local vector database for storing document chunks without API keys
"""

import os
from typing import List, Dict, Any, Optional
import chromadb
from langchain.schema import Document as LangchainDocument


class ChromaVectorStore:
    """Manages document storage and retrieval in ChromaDB"""

    def __init__(self, persist_directory: str = "backend/data/chroma_db"):
        """
        Initialize ChromaDB client with new API

        Args:
            persist_directory: Directory to persist ChromaDB files
        """
        self.persist_directory = persist_directory
        
        # Create persist directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB with new persistent client API
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection_name = "estatenexa_documents"
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        print(f"✓ Initialized ChromaDB in: {persist_directory}")
        print(f"✓ Using collection: {self.collection_name}")

    def add_documents(
        self, documents: List[LangchainDocument], metadata_filter: Optional[Dict] = None
    ) -> bool:
        """
        Add documents to ChromaDB

        Args:
            documents: List of LangChain Document objects
            metadata_filter: Optional metadata for filtering

        Returns:
            True if successful
        """
        try:
            ids = []
            texts = []
            metadatas = []
            
            for i, doc in enumerate(documents):
                doc_id = f"{metadata_filter.get('source', 'doc')}_{i}" if metadata_filter else f"doc_{i}"
                ids.append(doc_id)
                texts.append(doc.page_content)
                
                # Combine document metadata with filter metadata
                metadata = dict(doc.metadata) if doc.metadata else {}
                if metadata_filter:
                    metadata.update(metadata_filter)
                metadatas.append(metadata)
            
            # Add to collection
            self.collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
            )
            
            print(f"✓ Added {len(documents)} documents to ChromaDB")
            return True

        except Exception as e:
            print(f"✗ Error adding documents to ChromaDB: {str(e)}")
            return False

    def search_documents(
        self, query: str, top_k: int = 5, filters: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for documents in ChromaDB

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of matching documents with scores
        """
        try:
            # Search with filters if provided
            if filters:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=filters,
                )
            else:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=top_k,
                )
            
            formatted_results = []
            
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    
                    # Convert Chroma distance to similarity score (0-1)
                    # Chroma returns distances, lower is better for cosine
                    similarity = 1 - distance
                    
                    formatted_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "score": float(similarity),
                    })
            
            return formatted_results

        except Exception as e:
            print(f"✗ Error searching documents: {str(e)}")
            return []

    def delete_all(self) -> bool:
        """Delete all documents in collection"""
        try:
            # Delete the collection and recreate it
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"✓ Cleared collection: {self.collection_name}")
            return True
        except Exception as e:
            print(f"✗ Error clearing collection: {str(e)}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_directory": self.persist_directory,
            }
        except Exception as e:
            print(f"✗ Error getting collection stats: {str(e)}")
            return {}

    def persist(self) -> bool:
        """Persist the database to disk (auto-persisted with PersistentClient)"""
        try:
            # PersistentClient auto-persists, so no manual persist needed
            print(f"✓ ChromaDB auto-persisting to: {self.persist_directory}")
            return True
        except Exception as e:
            print(f"✗ Error with ChromaDB: {str(e)}")
            return False


# Initialize vector store
def get_chroma_store(persist_directory: str = "backend/data/chroma_db") -> ChromaVectorStore:
    """Get or create ChromaDB vector store"""
    try:
        return ChromaVectorStore(persist_directory)
    except Exception as e:
        print(f"✗ Error initializing ChromaDB: {str(e)}")
        raise
