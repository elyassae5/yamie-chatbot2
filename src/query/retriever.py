"""
Retriever module - handles vector similarity search in Pinecone.
Retrieves relevant document chunks for a given question with comprehensive logging.

SUPPORTS MULTI-NAMESPACE QUERIES:
- Can search a single namespace
- Can search multiple namespaces and merge results
- Useful for multi-brand/multi-source setups
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
    
    Supports:
    - Single namespace queries (default behavior)
    - Multi-namespace queries (search across brands/sources)
    
    Uses vector similarity search to find the most relevant document chunks
    for a given question. Integrates with LlamaIndex for seamless querying.
    """
    
    def __init__(self, config: Config = None, namespaces: Optional[List[str]] = None):
        """
        Initialize the retriever.
        
        Args:
            config: Optional configuration object (uses default if not provided)
            namespaces: Optional list of namespaces to search. 
                       If None, uses config.pinecone_namespace (single namespace mode).
                       If provided, searches all listed namespaces (multi-namespace mode).
        """
        self.config = config or get_config()
        
        # Determine which namespaces to search
        if namespaces:
            self.namespaces = namespaces
        else:
            self.namespaces = [self.config.pinecone_namespace]
        
        self.multi_namespace_mode = len(self.namespaces) > 1
        
        # Store index per namespace
        self._indexes = {}
        self._pinecone_client = None
        self._embed_model = None
        
        self._initialize()
    
    def _initialize(self):
        """
        Initialize connection to Pinecone and create indexes for all namespaces.
        """
        logger.info(
            "retriever_initialization_started",
            index_name=self.config.pinecone_index_name,
            namespaces=self.namespaces,
            multi_namespace_mode=self.multi_namespace_mode
        )
        
        try:
            # Connect to Pinecone
            self._pinecone_client = Pinecone(api_key=self.config.pinecone_api_key)
            logger.debug("pinecone_client_created")
            
            # Verify index exists
            existing_indexes = self._pinecone_client.list_indexes().names()
            
            if self.config.pinecone_index_name not in existing_indexes:
                error_msg = (
                    f"Index '{self.config.pinecone_index_name}' not found. "
                    f"Available indexes: {existing_indexes}. "
                    f"Run ingestion first to create the index!"
                )
                logger.error(
                    "index_not_found",
                    requested_index=self.config.pinecone_index_name,
                    available_indexes=existing_indexes
                )
                raise ValueError(error_msg)
            
            # Get Pinecone index
            pinecone_index = self._pinecone_client.Index(self.config.pinecone_index_name)
            
            # Check which namespaces have vectors
            stats = pinecone_index.describe_index_stats()
            available_namespaces = stats.get('namespaces', {})
            
            # Create embedding model (shared across all namespaces)
            self._embed_model = OpenAIEmbedding(
                model=self.config.embedding_model,
                dimensions=self.config.embedding_dimensions,
            )
            
            # Initialize index for each namespace
            valid_namespaces = []
            for namespace in self.namespaces:
                namespace_stats = available_namespaces.get(namespace, {})
                vector_count = namespace_stats.get('vector_count', 0)
                
                if vector_count == 0:
                    logger.warning(
                        "namespace_empty",
                        namespace=namespace,
                        vector_count=0,
                        message="Skipping empty namespace"
                    )
                    continue
                
                # Create vector store for this namespace
                vector_store = PineconeVectorStore(
                    pinecone_index=pinecone_index,
                    namespace=namespace,
                )
                
                # Create LlamaIndex index
                index = VectorStoreIndex.from_vector_store(
                    vector_store=vector_store,
                    embed_model=self._embed_model,
                )
                
                self._indexes[namespace] = index
                valid_namespaces.append(namespace)
                
                logger.info(
                    "namespace_initialized",
                    namespace=namespace,
                    vector_count=vector_count
                )
            
            if not self._indexes:
                error_msg = (
                    f"No valid namespaces found. Requested: {self.namespaces}. "
                    f"Available namespaces with vectors: {list(available_namespaces.keys())}. "
                    f"Run ingestion first!"
                )
                logger.error("no_valid_namespaces", requested=self.namespaces)
                raise ValueError(error_msg)
            
            # Update namespaces to only valid ones
            self.namespaces = valid_namespaces
            self.multi_namespace_mode = len(self.namespaces) > 1
            
            logger.info(
                "retriever_initialized",
                status="success",
                index_name=self.config.pinecone_index_name,
                active_namespaces=self.namespaces,
                multi_namespace_mode=self.multi_namespace_mode
            )
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "retriever_initialization_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Retriever initialization failed: {e}")
    

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            PineconeException,
            ConnectionError,
            TimeoutError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _retrieve_from_namespace(self, namespace: str, question: str, top_k: int):
        """
        Retrieve nodes from a single namespace with retry logic.
        """
        if namespace not in self._indexes:
            logger.warning("namespace_not_available", namespace=namespace)
            return []
        
        index = self._indexes[namespace]
        retriever = index.as_retriever(similarity_top_k=top_k)
        
        logger.debug("retrieving_from_namespace", namespace=namespace, top_k=top_k)
        nodes = retriever.retrieve(question)
        
        # Tag nodes with their namespace
        for node in nodes:
            node.metadata['_namespace'] = namespace
        
        return nodes
    
    def retrieve(self, request: QueryRequest) -> List[RetrievedChunk]:
        """
        Retrieve relevant chunks for a question using vector similarity search.
        
        For multi-namespace mode:
        - Queries each namespace separately
        - Merges and re-ranks results by similarity score
        - Returns top_k results across all namespaces
        
        Args:
            request: QueryRequest with question and retrieval parameters
            
        Returns:
            List of RetrievedChunk objects, sorted by relevance (highest first)
        """
        if not self._indexes:
            error_msg = "Retriever not initialized. No valid namespaces available."
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
            namespaces=self.namespaces,
            multi_namespace_mode=self.multi_namespace_mode,
            category_filter=request.category_filter
        )
        logger.debug("retrieval_question", question=request.question)
        
        try:
            all_nodes = []
            
            if self.multi_namespace_mode:
                # Multi-namespace: query each namespace and merge
                # Request more results per namespace to ensure good coverage
                per_namespace_k = max(request.top_k, 5)
                
                for namespace in self.namespaces:
                    nodes = self._retrieve_from_namespace(
                        namespace=namespace,
                        question=request.question,
                        top_k=per_namespace_k
                    )
                    all_nodes.extend(nodes)
                    
                    logger.debug(
                        "namespace_results",
                        namespace=namespace,
                        count=len(nodes)
                    )
            else:
                # Single namespace: standard retrieval
                namespace = self.namespaces[0]
                all_nodes = self._retrieve_from_namespace(
                    namespace=namespace,
                    question=request.question,
                    top_k=request.top_k
                )
            
            if not all_nodes:
                logger.warning("retrieval_empty", message="No chunks retrieved")
                return []
            
            logger.debug(
                "raw_nodes_retrieved",
                count=len(all_nodes),
                from_namespaces=len(self.namespaces) if self.multi_namespace_mode else 1
            )
            
            # Convert nodes to RetrievedChunk objects with filtering
            chunks = self._process_nodes(all_nodes, request)
            
            # Sort by similarity score (highest first)
            chunks.sort(key=lambda x: x.similarity_score, reverse=True)
            
            # Trim to requested top_k
            chunks = chunks[:request.top_k]
            
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
        """
        chunks = []
        filtered_count = 0
        
        for node in nodes:
            # Extract metadata
            source = node.metadata.get('file_name', 'unknown')
            
            # Try to get source_path for Notion documents (more descriptive)
            source_path = node.metadata.get('source_path')
            if source_path:
                source = source_path
            
            category = node.metadata.get('category', 'general')
            similarity_score = node.score if node.score is not None else 0.0
            namespace = node.metadata.get('_namespace', 'unknown')
            
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
                metadata={
                    **node.metadata,
                    'namespace': namespace,
                },
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
        """
        if not chunks:
            return
        
        # Get unique sources
        sources = list(set(c.source for c in chunks))
        logger.info(
            "retrieval_sources",
            sources=sources[:5],  # Limit to first 5
            unique_source_count=len(sources)
        )
        
        # Show top 4 similarity scores
        top_scores = [round(c.similarity_score, 3) for c in chunks[:4]]
        logger.info(
            "retrieval_top_scores",
            top_4_scores=top_scores
        )
        
        # Namespace distribution (for multi-namespace mode)
        if self.multi_namespace_mode:
            namespaces = {}
            for chunk in chunks:
                ns = chunk.metadata.get('namespace', 'unknown')
                namespaces[ns] = namespaces.get(ns, 0) + 1
            
            logger.info(
                "namespace_distribution",
                distribution=namespaces
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
    
    def get_stats(self) -> dict:
        """
        Get statistics about the vector store.
        """
        logger.debug("fetching_index_statistics")
        
        try:
            pinecone_index = self._pinecone_client.Index(self.config.pinecone_index_name)
            stats = pinecone_index.describe_index_stats()
            
            # Get stats for each namespace
            namespace_stats = {}
            for ns in self.namespaces:
                ns_data = stats.get('namespaces', {}).get(ns, {})
                namespace_stats[ns] = ns_data.get('vector_count', 0)
            
            result = {
                'total_vectors': stats.get('total_vector_count', 0),
                'dimension': stats.get('dimension', 0),
                'active_namespaces': self.namespaces,
                'namespace_vectors': namespace_stats,
                'multi_namespace_mode': self.multi_namespace_mode,
            }
            
            logger.debug("index_stats_fetched", **result)
            return result
            
        except Exception as e:
            logger.error(
                "index_stats_fetch_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            return {}
    
    def add_namespace(self, namespace: str) -> bool:
        """
        Dynamically add a namespace to search.
        
        Args:
            namespace: Namespace to add
            
        Returns:
            True if successfully added, False if namespace is empty/invalid
        """
        if namespace in self.namespaces:
            logger.info("namespace_already_active", namespace=namespace)
            return True
        
        try:
            pinecone_index = self._pinecone_client.Index(self.config.pinecone_index_name)
            stats = pinecone_index.describe_index_stats()
            
            namespace_stats = stats.get('namespaces', {}).get(namespace, {})
            vector_count = namespace_stats.get('vector_count', 0)
            
            if vector_count == 0:
                logger.warning("cannot_add_empty_namespace", namespace=namespace)
                return False
            
            # Create vector store and index
            vector_store = PineconeVectorStore(
                pinecone_index=pinecone_index,
                namespace=namespace,
            )
            
            index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                embed_model=self._embed_model,
            )
            
            self._indexes[namespace] = index
            self.namespaces.append(namespace)
            self.multi_namespace_mode = len(self.namespaces) > 1
            
            logger.info(
                "namespace_added",
                namespace=namespace,
                vector_count=vector_count,
                total_namespaces=len(self.namespaces)
            )
            return True
            
        except Exception as e:
            logger.error("failed_to_add_namespace", namespace=namespace, error=str(e))
            return False
    
    def remove_namespace(self, namespace: str) -> bool:
        """
        Remove a namespace from search.
        
        Args:
            namespace: Namespace to remove
            
        Returns:
            True if removed, False if not found or is last namespace
        """
        if namespace not in self.namespaces:
            logger.warning("namespace_not_found", namespace=namespace)
            return False
        
        if len(self.namespaces) == 1:
            logger.error("cannot_remove_last_namespace", namespace=namespace)
            return False
        
        self.namespaces.remove(namespace)
        if namespace in self._indexes:
            del self._indexes[namespace]
        
        self.multi_namespace_mode = len(self.namespaces) > 1
        
        logger.info(
            "namespace_removed",
            namespace=namespace,
            remaining_namespaces=self.namespaces
        )
        return True


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_single_namespace_retriever(namespace: str = None, config: Config = None) -> Retriever:
    """
    Create a retriever for a single namespace.
    
    Args:
        namespace: Namespace to search (defaults to config.pinecone_namespace)
        config: Optional config object
        
    Returns:
        Configured Retriever instance
    """
    config = config or get_config()
    ns = namespace or config.pinecone_namespace
    return Retriever(config=config, namespaces=[ns])


def create_multi_namespace_retriever(namespaces: List[str], config: Config = None) -> Retriever:
    """
    Create a retriever that searches across multiple namespaces.
    
    Args:
        namespaces: List of namespaces to search
        config: Optional config object
        
    Returns:
        Configured Retriever instance
        
    Example:
        retriever = create_multi_namespace_retriever([
            "operations-department",
            "yamie-pastabar",
            "flaminwok"
        ])
    """
    config = config or get_config()
    return Retriever(config=config, namespaces=namespaces)


def create_all_namespaces_retriever(config: Config = None) -> Retriever:
    """
    Create a retriever that searches ALL available namespaces.
    
    Args:
        config: Optional config object
        
    Returns:
        Configured Retriever instance searching all namespaces
    """
    config = config or get_config()
    
    # Get all namespaces from Pinecone
    pc = Pinecone(api_key=config.pinecone_api_key)
    index = pc.Index(config.pinecone_index_name)
    stats = index.describe_index_stats()
    
    all_namespaces = list(stats.get('namespaces', {}).keys())
    
    if not all_namespaces:
        raise ValueError("No namespaces found in Pinecone index")
    
    logger.info("creating_all_namespace_retriever", namespaces=all_namespaces)
    
    return Retriever(config=config, namespaces=all_namespaces)