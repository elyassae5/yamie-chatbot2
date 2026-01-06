"""
Pinecone vector store initialization and management.
Handles index creation, namespace management, and StorageContext setup.
"""

import structlog
import time
from pinecone import Pinecone, ServerlessSpec
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import StorageContext

from src.config import Config

logger = structlog.get_logger(__name__)


def create_storage_context(config: Config, clear_namespace: bool = False) -> StorageContext:
    """
    Create and initialize Pinecone storage context for LlamaIndex.
    
    This function:
    1. Connects to Pinecone
    2. Creates index if it doesn't exist
    3. Optionally clears existing namespace data
    4. Returns configured StorageContext
    
    Args:
        config: Configuration object with Pinecone settings
        clear_namespace: If True, deletes all vectors in the namespace before proceeding
        
    Returns:
        StorageContext configured with Pinecone vector store
        
    Raises:
        ValueError: If API key is missing or invalid
        Exception: If Pinecone operations fail
    """
    logger.info(
        "pinecone_initialization_started",
        index=config.pinecone_index_name,
        namespace=config.pinecone_namespace
    )
    
    # Validate API key
    if not config.pinecone_api_key:
        error_msg = "Pinecone API key is missing in configuration"
        logger.error("pinecone_api_key_missing")
        raise ValueError(error_msg)
    
    # Initialize Pinecone client
    try:
        pc = Pinecone(api_key=config.pinecone_api_key)
        logger.debug("pinecone_client_initialized")
    except Exception as e:
        logger.error(
            "pinecone_client_initialization_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise ValueError(f"Invalid Pinecone API key or connection failed: {e}")
    
    # Check if index exists
    index_name = config.pinecone_index_name
    
    try:
        existing_indexes = pc.list_indexes().names()
        logger.debug(
            "pinecone_indexes_listed",
            existing_indexes_count=len(existing_indexes)
        )
    except Exception as e:
        logger.error(
            "pinecone_list_indexes_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise
    
    # Create index if it doesn't exist
    if index_name not in existing_indexes:
        logger.info(
            "pinecone_index_creation_started",
            index=index_name,
            dimension=config.embedding_dimensions,
            metric="cosine",
            cloud="aws",
            region="us-east-1"
        )
        
        try:
            pc.create_index(
                name=index_name,
                dimension=config.embedding_dimensions,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1",
                ),
            )
            logger.info(
                "pinecone_index_created",
                index=index_name,
                status="success"
            )
            
            # Wait for index to be ready (serverless indexes need initialization time)
            logger.info("pinecone_index_initialization", message="Waiting for index to be ready...")
            time.sleep(5)  # Give Pinecone time to initialize
            
        except Exception as e:
            logger.error(
                "pinecone_index_creation_failed",
                index=index_name,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    else:
        logger.info(
            "pinecone_index_exists",
            index=index_name
        )
    
    # Connect to index
    try:
        index = pc.Index(index_name)
        logger.debug(
            "pinecone_index_connected",
            index=index_name
        )
    except Exception as e:
        logger.error(
            "pinecone_index_connection_failed",
            index=index_name,
            error=str(e),
            error_type=type(e).__name__
        )
        raise
    
    # Log current index statistics
    try:
        stats = index.describe_index_stats()
        total_vectors = stats.get('total_vector_count', 0)
        namespaces = stats.get('namespaces', {})
        namespace_vectors = namespaces.get(config.pinecone_namespace, {}).get('vector_count', 0)
        
        logger.info(
            "pinecone_index_stats",
            total_vectors_all_namespaces=total_vectors,
            namespace=config.pinecone_namespace,
            namespace_vectors=namespace_vectors
        )
        
        if len(namespaces) > 1:
            logger.debug(
                "pinecone_other_namespaces",
                namespaces=list(namespaces.keys())
            )
            
    except Exception as e:
        logger.warning(
            "pinecone_stats_retrieval_failed",
            error=str(e),
            error_type=type(e).__name__
        )
    
    # Clear namespace if requested
    if clear_namespace:
        logger.info(
            "pinecone_namespace_clearing_started",
            namespace=config.pinecone_namespace
        )
        
        try:
            # Check if namespace exists and has vectors
            stats = index.describe_index_stats()
            namespaces = stats.get('namespaces', {})
            namespace_vectors = namespaces.get(config.pinecone_namespace, {}).get('vector_count', 0)
            
            if namespace_vectors > 0:
                logger.info(
                    "pinecone_namespace_deleting_vectors",
                    namespace=config.pinecone_namespace,
                    vectors_to_delete=namespace_vectors
                )
                index.delete(delete_all=True, namespace=config.pinecone_namespace)
                logger.info(
                    "pinecone_namespace_cleared",
                    namespace=config.pinecone_namespace,
                    status="success"
                )
            else:
                logger.info(
                    "pinecone_namespace_empty",
                    namespace=config.pinecone_namespace
                )
                
        except Exception as e:
            # Namespace might not exist yet - that's okay
            if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                logger.info(
                    "pinecone_namespace_not_exists",
                    namespace=config.pinecone_namespace,
                    message="Will be created during ingestion"
                )
            else:
                logger.error(
                    "pinecone_namespace_clear_failed",
                    namespace=config.pinecone_namespace,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
    
    # Create vector store wrapper
    try:
        vector_store = PineconeVectorStore(
            pinecone_index=index,
            namespace=config.pinecone_namespace,
        )
        logger.debug("pinecone_vector_store_created")
    except Exception as e:
        logger.error(
            "pinecone_vector_store_creation_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise
    
    # Create storage context
    try:
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        logger.info(
            "storage_context_initialized",
            status="success"
        )
        return storage_context
    except Exception as e:
        logger.error(
            "storage_context_creation_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise


def get_index_stats(config: Config) -> dict:
    """
    Get statistics about a Pinecone index.
    Useful for monitoring and debugging.
    
    Note: This is a utility function for future use.
    Currently used in system_status.py and retriever.py (could be refactored to use this).
    
    Args:
        config: Configuration object with Pinecone settings
        
    Returns:
        Dictionary with index statistics
    """
    try:
        pc = Pinecone(api_key=config.pinecone_api_key)
        index = pc.Index(config.pinecone_index_name)
        stats = index.describe_index_stats()
        
        logger.debug(
            "index_stats_retrieved",
            index=config.pinecone_index_name,
            total_vectors=stats.get('total_vector_count', 0)
        )
        
        return {
            'total_vectors': stats.get('total_vector_count', 0),
            'dimension': stats.get('dimension', 0),
            'namespaces': stats.get('namespaces', {}),
            'namespace_vectors': stats.get('namespaces', {}).get(
                config.pinecone_namespace, {}
            ).get('vector_count', 0)
        }
    except Exception as e:
        logger.error(
            "index_stats_retrieval_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        return {}