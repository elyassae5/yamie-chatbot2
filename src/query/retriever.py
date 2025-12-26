"""
Retriever module - handles vector similarity search in Pinecone.
Retrieves relevant document chunks for a given question.
"""

from typing import List, Optional
from pinecone import Pinecone
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding

from src.config import Config, get_config
from src.query.models import RetrievedChunk, QueryRequest


class Retriever:
    """
    Handles document retrieval from Pinecone vector store.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or get_config()
        self.index = None
        self._initialize()
        
    def _initialize(self):
        """Initialize connection to Pinecone and create LlamaIndex vector store index."""
        print(f"\n🔌 Connecting to Pinecone index: {self.config.pinecone_index_name}")
        
        try:
            # Connect to Pinecone
            pc = Pinecone(api_key=self.config.pinecone_api_key)
            
            # Verify index exists
            existing_indexes = pc.list_indexes().names()
            if self.config.pinecone_index_name not in existing_indexes:
                raise ValueError(
                    f"❌ Pinecone index '{self.config.pinecone_index_name}' not found.\n"
                    f"   Available indexes: {existing_indexes}\n"
                    f"   → Run ingestion first to create the index!"
                )
            
            # Get Pinecone index
            pinecone_index = pc.Index(self.config.pinecone_index_name)
            
            # Check if namespace has vectors
            stats = pinecone_index.describe_index_stats()
            namespace_count = stats.get('namespaces', {}).get(self.config.pinecone_namespace, {}).get('vector_count', 0)
            
            if namespace_count == 0:
                raise ValueError(
                    f"❌ Namespace '{self.config.pinecone_namespace}' is empty (0 vectors).\n"
                    f"   → Run ingestion first to populate the index!"
                )
            
            print(f"✅ Found {namespace_count} vectors in namespace '{self.config.pinecone_namespace}'")
            
            # Create vector store
            vector_store = PineconeVectorStore(
                pinecone_index=pinecone_index,
                namespace=self.config.pinecone_namespace,
            )
            
            # Create embedding model (must match ingestion!)
            embed_model = OpenAIEmbedding(
                model=self.config.embedding_model,
                dimensions=self.config.embedding_dimensions,
            )
            
            # Create LlamaIndex vector store index
            self.index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                embed_model=embed_model,
            )
            
            print("✅ Retriever initialized successfully")
            
        except Exception as e:
            print(f"\n❌ Error initializing retriever: {e}")
            raise
    
    def retrieve(self, request: QueryRequest) -> List[RetrievedChunk]:
        """
        Retrieve relevant chunks for a question.
        
        Args:
            request: QueryRequest with question and retrieval parameters
            
        Returns:
            List of RetrievedChunk objects, sorted by relevance (highest first)
        """
        if not self.index:
            raise RuntimeError("Retriever not initialized. Call _initialize() first.")
        
        # Validate request
        request.validate()
        
        print(f"\n🔍 Retrieving top {request.top_k} chunks for: '{request.question}'")
        
        try:
            # Create retriever from index
            retriever = self.index.as_retriever(
                similarity_top_k=request.top_k,
            )
            
            # Retrieve nodes
            nodes = retriever.retrieve(request.question)
            
            if not nodes:
                print("⚠️  No chunks retrieved (empty result)")
                return []
            
            # Convert nodes to RetrievedChunk objects
            chunks = []
            for node in nodes:
                # Extract metadata
                source = node.metadata.get('file_name', 'unknown')
                category = node.metadata.get('category', 'general')
                similarity_score = node.score if node.score is not None else 0.0
                
                # Apply similarity threshold filter
                if similarity_score < self.config.query_similarity_threshold:
                    continue
                
                # Apply category filter if specified
                if request.category_filter and category != request.category_filter:
                    continue
                
                chunk = RetrievedChunk(
                    text=node.text,
                    source=source,
                    category=category,
                    similarity_score=similarity_score,
                    metadata=node.metadata,
                )
                chunks.append(chunk)
            
            # Sort by similarity score (highest first)
            chunks.sort(key=lambda x: x.similarity_score, reverse=True)
            
            print(f"✅ Retrieved {len(chunks)} relevant chunks")
            
            # Show chunk sources for debugging
            if chunks:
                sources = list(set(c.source for c in chunks))
                print(f"   Sources: {', '.join(sources)}")
                print(f"   Similarity scores: {[f'{c.similarity_score:.3f}' for c in chunks[:3]]}")
            
            return chunks
            
        except Exception as e:
            print(f"\n❌ Error during retrieval: {e}")
            raise
    
    def get_stats(self) -> dict:
        """
        Get statistics about the vector store.
        Useful for debugging and monitoring.
        """
        try:
            pc = Pinecone(api_key=self.config.pinecone_api_key)
            pinecone_index = pc.Index(self.config.pinecone_index_name)
            stats = pinecone_index.describe_index_stats()
            
            return {
                'total_vectors': stats.get('total_vector_count', 0),
                'namespace': self.config.pinecone_namespace,
                'namespace_vectors': stats.get('namespaces', {}).get(self.config.pinecone_namespace, {}).get('vector_count', 0),
                'dimension': stats.get('dimension', 0),
            }
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {}