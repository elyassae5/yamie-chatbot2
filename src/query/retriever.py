"""
Retriever module - handles vector similarity search in Pinecone.
Retrieves relevant document chunks for a given question with comprehensive logging.
"""

import structlog
import logging
from typing import List, Optional
from pinecone import Pinecone

from pinecone.exceptions import PineconeException

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding

from src.config import Config, get_config
from src.query.models import RetrievedChunk, QueryRequest

logger = structlog.get_logger(__name__)


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
        logger.info(
            "retriever_initialization_started",
            index_name=self.config.pinecone_index_name,
            namespace=self.config.pinecone_namespace
        )
        
        try:
            # Connect to Pinecone
            pc = Pinecone(api_key=self.config.pinecone_api_key)
            logger.debug("pinecone_client_created")
            
            # Verify index exists
            existing_indexes = pc.list_indexes().names()
            
            if self.config.pinecone_index_name not in existing_indexes:
                error_msg = (
                    f"Index '{self.config.pinecone_index_name}' not found. "
                    f"Available indexes: {existing_indexes}. "
                    f"Run ingestion first to create the index!"
                )
                logger.error(
                    "index_not_found",
                    requested_index=self.config.pinecone_index_name,
                    available_indexes=existing_indexes,
                    error_message=error_msg
                )
                raise ValueError(error_msg)
            
            logger.debug(
                "index_verified",
                index_name=self.config.pinecone_index_name
            )
            
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
                logger.error(
                    "namespace_empty",
                    namespace=self.config.pinecone_namespace,
                    vector_count=0,
                    error_message=error_msg
                )
                raise ValueError(error_msg)
            
            logger.info(
                "namespace_verified",
                namespace=self.config.pinecone_namespace,
                vector_count=namespace_count
            )
            
            # Create vector store
            vector_store = PineconeVectorStore(
                pinecone_index=pinecone_index,
                namespace=self.config.pinecone_namespace,
            )
            logger.debug("pinecone_vector_store_created")
            
            # Create embedding model (must match ingestion!)
            embed_model = OpenAIEmbedding(
                model=self.config.embedding_model,
                dimensions=self.config.embedding_dimensions,
            )
            logger.debug(
                "embedding_model_initialized",
                model=self.config.embedding_model,
                dimensions=self.config.embedding_dimensions
            )
            
            # Create LlamaIndex vector store index
            self.index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                embed_model=embed_model,
            )
            
            logger.info(
                "retriever_initialized",
                status="success",
                index_name=self.config.pinecone_index_name,
                namespace=self.config.pinecone_namespace,
                vector_count=namespace_count
            )
            
        except ValueError as e:
            # Re-raise ValueError (already has good message)
            raise
        except Exception as e:
            logger.error(
                "retriever_initialization_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Retriever initialization failed: {e}")
    

    @retry(
        stop=stop_after_attempt(3),  # Try up to 3 times
        wait=wait_exponential(multiplier=1, min=2, max=10),  # Wait 2s, 4s, 8s
        retry=retry_if_exception_type((
            PineconeException,
            ConnectionError,
            TimeoutError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _retrieve_with_retry(self, retriever, question: str):
        """
        Retrieve nodes from Pinecone with automatic retry on transient failures.
        
        Retry strategy:
        - Up to 3 attempts total
        - Exponential backoff: 2s, 4s, 8s between retries
        - Only retry on: Connection errors, timeouts, Pinecone exceptions
        
        Args:
            retriever: LlamaIndex retriever object
            question: Question to search for
            
        Returns:
            List of retrieved nodes
            
        Raises:
            Exception: If all retries fail
        """
        logger.debug("pinecone_retrieval_attempt", question=question)
        
        nodes = retriever.retrieve(question)
        
        logger.debug("pinecone_retrieval_successful", nodes_count=len(nodes) if nodes else 0)
        
        return nodes
    
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
            logger.error("retriever_not_initialized")
            raise RuntimeError(error_msg)
        
        # Validate request
        try:
            request.validate()
        except ValueError as e:
            logger.error(
                "invalid_query_request",
                error=str(e),
                question=request.question
            )
            raise
        
        logger.info(
            "retrieval_started",
            top_k=request.top_k,
            category_filter=request.category_filter
        )
        logger.debug("retrieval_question", question=request.question)
        
        if request.category_filter:
            logger.debug(
                "category_filter_applied",
                category=request.category_filter
            )
        
        try:
            # Create retriever from index
            retriever = self.index.as_retriever(
                similarity_top_k=request.top_k,
            )
            
            # Retrieve nodes (with automatic retry on failures)
            nodes = self._retrieve_with_retry(retriever, request.question)
            
            if not nodes:
                logger.warning("retrieval_empty", message="No chunks retrieved")
                return []
            
            logger.debug(
                "raw_nodes_retrieved",
                count=len(nodes)
            )
            
            # Convert nodes to RetrievedChunk objects with filtering
            chunks = self._process_nodes(nodes, request)
            
            # Sort by similarity score (highest first)
            chunks.sort(key=lambda x: x.similarity_score, reverse=True)
            
            logger.info(
                "retrieval_completed",
                chunks_count=len(chunks),
                top_k_requested=request.top_k
            )
            
            # Log retrieval details
            self._log_retrieval_details(chunks)
            
            return chunks
            
        except Exception as e:
            logger.error(
                "retrieval_failed",
                error=str(e),
                error_type=type(e).__name__,
                question=request.question
            )
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
                    "chunk_filtered_by_threshold",
                    source=source,
                    score=round(similarity_score, 3),
                    threshold=self.config.query_similarity_threshold
                )
                filtered_count += 1
                continue
            
            # Apply category filter if specified
            if request.category_filter and category != request.category_filter:
                logger.debug(
                    "chunk_filtered_by_category",
                    source=source,
                    chunk_category=category,
                    requested_category=request.category_filter
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
            logger.debug(
                "chunks_filtered",
                filtered_count=filtered_count,
                remaining_count=len(chunks)
            )
        
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
        logger.info(
            "retrieval_sources",
            sources=sources,
            unique_source_count=len(sources)
        )
        
        # Show top 4 similarity scores
        top_scores = [round(c.similarity_score, 3) for c in chunks[:4]]
        logger.info(
            "retrieval_top_scores",
            top_4_scores=top_scores
        )
        
        # Category distribution
        categories = {}
        for chunk in chunks:
            categories[chunk.category] = categories.get(chunk.category, 0) + 1
        
        if len(categories) > 1:
            logger.debug(
                "category_distribution",
                categories=categories
            )
        
        # Score range
        if len(chunks) > 1:
            min_score = min(c.similarity_score for c in chunks)
            max_score = max(c.similarity_score for c in chunks)
            logger.debug(
                "score_range",
                min_score=round(min_score, 3),
                max_score=round(max_score, 3)
            )
    
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
        logger.debug("fetching_index_statistics")
        
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
            
            logger.debug(
                "index_stats_fetched",
                total_vectors=result['total_vectors'],
                namespace=result['namespace'],
                namespace_vectors=result['namespace_vectors'],
                dimension=result['dimension']
            )
            return result
            
        except Exception as e:
            logger.error(
                "index_stats_fetch_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            return {}