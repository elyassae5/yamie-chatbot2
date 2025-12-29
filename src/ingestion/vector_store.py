"""
Pinecone vector store initialization and management.
Handles index creation, namespace management, and StorageContext setup.
"""

import logging
import time
from pinecone import Pinecone, ServerlessSpec
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import StorageContext

from src.config import Config

logger = logging.getLogger(__name__)


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
    logger.info(f"Initializing Pinecone connection...")
    logger.info(f"  Index: {config.pinecone_index_name}")
    logger.info(f"  Namespace: {config.pinecone_namespace}")
    
    # Validate API key
    if not config.pinecone_api_key:
        error_msg = "Pinecone API key is missing in configuration"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Initialize Pinecone client
    try:
        pc = Pinecone(api_key=config.pinecone_api_key)
        logger.debug("Pinecone client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Pinecone client: {e}")
        raise ValueError(f"Invalid Pinecone API key or connection failed: {e}")
    
    # Check if index exists
    index_name = config.pinecone_index_name
    
    try:
        existing_indexes = pc.list_indexes().names()
        logger.debug(f"Found {len(existing_indexes)} existing index(es)")
    except Exception as e:
        logger.error(f"Failed to list Pinecone indexes: {e}")
        raise
    
    # Create index if it doesn't exist
    if index_name not in existing_indexes:
        logger.info(f"Index '{index_name}' not found - creating new index...")
        logger.info(f"  Dimension: {config.embedding_dimensions}")
        logger.info(f"  Metric: cosine")
        logger.info(f"  Cloud: AWS (us-east-1)")
        
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
            logger.info(f"✓ Index '{index_name}' created successfully")
            
            # Wait for index to be ready (serverless indexes need initialization time)
            logger.info("Waiting for index to be ready...")
            time.sleep(5)  # Give Pinecone time to initialize
            
        except Exception as e:
            logger.error(f"Failed to create index '{index_name}': {e}")
            raise
    else:
        logger.info(f"✓ Index '{index_name}' already exists")
    
    # Connect to index
    try:
        index = pc.Index(index_name)
        logger.debug(f"Connected to index '{index_name}'")
    except Exception as e:
        logger.error(f"Failed to connect to index '{index_name}': {e}")
        raise
    
    # Log current index statistics
    try:
        stats = index.describe_index_stats()
        total_vectors = stats.get('total_vector_count', 0)
        namespaces = stats.get('namespaces', {})
        namespace_vectors = namespaces.get(config.pinecone_namespace, {}).get('vector_count', 0)
        
        logger.info(f"Current index stats:")
        logger.info(f"  Total vectors (all namespaces): {total_vectors}")
        logger.info(f"  Vectors in '{config.pinecone_namespace}': {namespace_vectors}")
        
        if len(namespaces) > 1:
            logger.debug(f"  Other namespaces: {list(namespaces.keys())}")
            
    except Exception as e:
        logger.warning(f"Could not retrieve index stats: {e}")
    
    # Clear namespace if requested
    if clear_namespace:
        logger.info(f"Clearing namespace '{config.pinecone_namespace}'...")
        
        try:
            # Check if namespace exists and has vectors
            stats = index.describe_index_stats()
            namespaces = stats.get('namespaces', {})
            namespace_vectors = namespaces.get(config.pinecone_namespace, {}).get('vector_count', 0)
            
            if namespace_vectors > 0:
                logger.info(f"  Deleting {namespace_vectors} existing vector(s)...")
                index.delete(delete_all=True, namespace=config.pinecone_namespace)
                logger.info(f"✓ Namespace '{config.pinecone_namespace}' cleared")
            else:
                logger.info(f"  Namespace '{config.pinecone_namespace}' is empty or doesn't exist yet")
                
        except Exception as e:
            # Namespace might not exist yet - that's okay
            if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                logger.info(f"  Namespace '{config.pinecone_namespace}' doesn't exist yet - will be created during ingestion")
            else:
                logger.error(f"Failed to clear namespace: {e}")
                raise
    
    # Create vector store wrapper
    try:
        vector_store = PineconeVectorStore(
            pinecone_index=index,
            namespace=config.pinecone_namespace,
        )
        logger.debug("PineconeVectorStore created")
    except Exception as e:
        logger.error(f"Failed to create PineconeVectorStore: {e}")
        raise
    
    # Create storage context
    try:
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        logger.info("✓ Storage context initialized successfully")
        return storage_context
    except Exception as e:
        logger.error(f"Failed to create StorageContext: {e}")
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
        
        return {
            'total_vectors': stats.get('total_vector_count', 0),
            'dimension': stats.get('dimension', 0),
            'namespaces': stats.get('namespaces', {}),
            'namespace_vectors': stats.get('namespaces', {}).get(
                config.pinecone_namespace, {}
            ).get('vector_count', 0)
        }
    except Exception as e:
        logger.error(f"Failed to get index stats: {e}")
        return {}