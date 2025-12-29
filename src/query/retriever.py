"""
Retriever module - handles vector similarity search in Pinecone.
Retrieves relevant document chunks for a given question with comprehensive logging.
"""

import logging
from typing import List, Optional
from pinecone import Pinecone
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding

from src.config import Config, get_config
from src.query.models import RetrievedChunk, QueryRequest

logger = logging.getLogger(__name__)


class Retriever:
    """
    Handles document retrieval from Pinecone vector store.
    
    Uses vector similarity search to find the most relevant document chunks
    for a given question. Integrates with LlamaIndex for seamless querying.
    """
    
    def __init__(self, config: Config = None):
        """
        Initialize the retriever.
        
        Args:
            config: Optional configuration object (uses default if not provided)
        """
        self.config = config or get_config()
        self.index = None
        self._initialize()
        
    def _initialize(self):
        """
        Initialize connection to Pinecone and create LlamaIndex vector store index.
        
        This method:
        1. Connects to Pinecone
        2. Verifies the index exists
        3. Checks that the namespace has vectors
        4. Creates the LlamaIndex retriever
        
        Raises:
            ValueError: If index doesn't exist or namespace is empty
            Exception: If connection or initialization fails
        """
        logger.info(f"Initializing retriever for index: {self.config.pinecone_index_name}")
        logger.info(f"Namespace: {self.config.pinecone_namespace}")
        
        try:
            # Connect to Pinecone
            pc = Pinecone(api_key=self.config.pinecone_api_key)
            logger.debug("Pinecone client created")
            
            # Verify index exists
            existing_indexes = pc.list_indexes().names()
            
            if self.config.pinecone_index_name not in existing_indexes:
                error_msg = (
                    f"Index '{self.config.pinecone_index_name}' not found. "
                    f"Available indexes: {existing_indexes}. "
                    f"Run ingestion first to create the index!"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.debug(f"Index '{self.config.pinecone_index_name}' exists")
            
            # Get Pinecone index
            pinecone_index = pc.Index(self.config.pinecone_index_name)
            
            # Check if namespace has vectors
            stats = pinecone_index.describe_index_stats()
            namespace_count = stats.get('namespaces', {}).get(
                self.config.pinecone_namespace, {}
            ).get('vector_count', 0)
            
            if namespace_count == 0:
                error_msg = (
                    f"Namespace '{self.config.pinecone_namespace}' is empty (0 vectors). "
                    f"Run ingestion first to populate the index!"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.info(f"✓ Found {namespace_count} vectors in namespace '{self.config.pinecone_namespace}'")
            
            # Create vector store
            vector_store = PineconeVectorStore(
                pinecone_index=pinecone_index,
                namespace=self.config.pinecone_namespace,
            )
            logger.debug("PineconeVectorStore created")
            
            # Create embedding model (must match ingestion!)
            embed_model = OpenAIEmbedding(
                model=self.config.embedding_model,
                dimensions=self.config.embedding_dimensions,
            )
            logger.debug(f"Embedding model initialized: {self.config.embedding_model}")
            
            # Create LlamaIndex vector store index
            self.index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                embed_model=embed_model,
            )
            
            logger.info("✓ Retriever initialized successfully")
            
        except ValueError as e:
            # Re-raise ValueError (already has good message)
            raise
        except Exception as e:
            logger.error(f"Failed to initialize retriever: {e}", exc_info=True)
            raise RuntimeError(f"Retriever initialization failed: {e}")
    
    def retrieve(self, request: QueryRequest) -> List[RetrievedChunk]:
        """
        Retrieve relevant chunks for a question using vector similarity search.
        
        Process:
        1. Validate the request
        2. Embed the question (via LlamaIndex)
        3. Search Pinecone for similar vectors
        4. Filter by similarity threshold and category
        5. Return sorted results
        
        Args:
            request: QueryRequest with question and retrieval parameters
            
        Returns:
            List of RetrievedChunk objects, sorted by relevance (highest first)
            
        Raises:
            RuntimeError: If retriever not initialized
            ValueError: If request validation fails
            Exception: If retrieval fails
        """
        if not self.index:
            error_msg = "Retriever not initialized. Call _initialize() first."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Validate request
        try:
            request.validate()
        except ValueError as e:
            logger.error(f"Invalid query request: {e}")
            raise
        
        logger.info(f"Retrieving top {request.top_k} chunks")
        logger.debug(f"Question: '{request.question}'")
        
        if request.category_filter:
            logger.debug(f"Category filter: {request.category_filter}")
        
        try:
            # Create retriever from index
            retriever = self.index.as_retriever(
                similarity_top_k=request.top_k,
            )
            
            # Retrieve nodes
            nodes = retriever.retrieve(request.question)
            
            if not nodes:
                logger.warning("No chunks retrieved (empty result)")
                return []
            
            logger.debug(f"Retrieved {len(nodes)} raw nodes from Pinecone")
            
            # Convert nodes to RetrievedChunk objects with filtering
            chunks = self._process_nodes(nodes, request)
            
            # Sort by similarity score (highest first)
            chunks.sort(key=lambda x: x.similarity_score, reverse=True)
            
            logger.info(f"✓ Retrieved {len(chunks)} relevant chunks")
            
            # Log retrieval details
            self._log_retrieval_details(chunks)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Retrieval failed: {e}", exc_info=True)
            raise
    
    def _process_nodes(self, nodes, request: QueryRequest) -> List[RetrievedChunk]:
        """
        Process raw nodes from Pinecone into RetrievedChunk objects.
        Applies filtering based on similarity threshold and category.
        
        Args:
            nodes: Raw nodes from LlamaIndex retriever
            request: Original query request
            
        Returns:
            List of filtered and processed RetrievedChunk objects
        """
        chunks = []
        filtered_count = 0
        
        for node in nodes:
            # Extract metadata
            source = node.metadata.get('file_name', 'unknown')
            category = node.metadata.get('category', 'general')
            similarity_score = node.score if node.score is not None else 0.0
            
            # Apply similarity threshold filter
            if similarity_score < self.config.query_similarity_threshold:
                logger.debug(
                    f"Filtered out chunk from {source}: "
                    f"score {similarity_score:.3f} < threshold {self.config.query_similarity_threshold}"
                )
                filtered_count += 1
                continue
            
            # Apply category filter if specified
            if request.category_filter and category != request.category_filter:
                logger.debug(
                    f"Filtered out chunk from {source}: "
                    f"category '{category}' != requested '{request.category_filter}'"
                )
                filtered_count += 1
                continue
            
            # Create chunk object
            chunk = RetrievedChunk(
                text=node.text,
                source=source,
                category=category,
                similarity_score=similarity_score,
                metadata=node.metadata,
            )
            chunks.append(chunk)
        
        if filtered_count > 0:
            logger.debug(f"Filtered out {filtered_count} chunks based on threshold/category")
        
        return chunks
    
    def _log_retrieval_details(self, chunks: List[RetrievedChunk]) -> None:
        """
        Log detailed information about retrieved chunks.
        Useful for debugging and monitoring retrieval quality.
        
        Args:
            chunks: List of retrieved chunks
        """
        if not chunks:
            return
        
        # Get unique sources
        sources = list(set(c.source for c in chunks))
        logger.info(f"Sources: {', '.join(sources)}")
        
        # Show top 4 similarity scores
        top_scores = [f"{c.similarity_score:.3f}" for c in chunks[:4]]
        logger.info(f"Top 4 scores: {top_scores}")
        
        # Category distribution
        categories = {}
        for chunk in chunks:
            categories[chunk.category] = categories.get(chunk.category, 0) + 1
        
        if len(categories) > 1:
            logger.debug(f"Category distribution: {categories}")
        
        # Score range
        if len(chunks) > 1:
            min_score = min(c.similarity_score for c in chunks)
            max_score = max(c.similarity_score for c in chunks)
            logger.debug(f"Score range: {min_score:.3f} - {max_score:.3f}")
    
    def get_stats(self) -> dict:
        """
        Get statistics about the vector store.
        Useful for debugging and monitoring.
        
        Returns:
            Dictionary with index statistics:
            - total_vectors: Total vectors across all namespaces
            - namespace: Current namespace name
            - namespace_vectors: Vectors in current namespace
            - dimension: Vector dimension
        """
        logger.debug("Fetching index statistics")
        
        try:
            pc = Pinecone(api_key=self.config.pinecone_api_key)
            pinecone_index = pc.Index(self.config.pinecone_index_name)
            stats = pinecone_index.describe_index_stats()
            
            result = {
                'total_vectors': stats.get('total_vector_count', 0),
                'namespace': self.config.pinecone_namespace,
                'namespace_vectors': stats.get('namespaces', {}).get(
                    self.config.pinecone_namespace, {}
                ).get('vector_count', 0),
                'dimension': stats.get('dimension', 0),
            }
            
            logger.debug(f"Index stats: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}", exc_info=True)
            return {}