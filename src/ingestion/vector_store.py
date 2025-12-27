"""
Pinecone vector store initialization.
Creates a StorageContext for LlamaIndex.
"""

from pinecone import Pinecone, ServerlessSpec
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import StorageContext

from src.config import Config


def create_storage_context(config: Config, clear_namespace: bool = False) -> StorageContext:
    print(f"Initializing Pinecone index: {config.pinecone_index_name}")

    pc = Pinecone(api_key=config.pinecone_api_key)

    index_name = config.pinecone_index_name
    existing_indexes = pc.list_indexes().names()

    if index_name not in existing_indexes:
        print(f"Creating index '{index_name}'")
        pc.create_index(
            name=index_name,
            dimension=config.embedding_dimensions,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1",
            ),
        )

    index = pc.Index(index_name)

    if clear_namespace:
        try:
            print(f"Clearing namespace '{config.pinecone_namespace}'")
            index.delete(delete_all=True, namespace=config.pinecone_namespace)
        except Exception as e:
            if "not found" in str(e).lower():
                print(f"Namespace '{config.pinecone_namespace}' doesn't exist yet - will create it")
            else:
                raise  # Re-raise if it's a different error
            

    vector_store = PineconeVectorStore(
        pinecone_index=index,
        namespace=config.pinecone_namespace,
    )

    return StorageContext.from_defaults(vector_store=vector_store)
