import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    data_dir: str = "./data"
    supported_extensions: list[str] = field(default_factory=lambda: [".docx"])

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072
    embedding_batch_size: int = 100

    # Pinecone
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY", "")
    pinecone_index_name: str = os.getenv("PINECONE_INDEX_NAME", "yamie-test")
    pinecone_namespace: str = "test-data"

    # Chunking
    chunk_size: int = 500
    chunk_overlap: int = 150

    # Query/Retrieval Settings
    query_top_k: int = 9                  # Number of chunks to retrieve
    query_similarity_threshold: float = 0.0
    
    # LLM Settings
    llm_model: str = "gpt-4o-mini"               # OpenAI model for generation
    llm_temperature: float = 0.3            # Low = more factual, high = more creative
    llm_max_tokens: int = 450               # Max response length

    # Redis Settings (for caching + conversation memory)
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    redis_db: int = 0  # Database number (0-15)
    
    # Supabase Settings (for logging)
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")

    # Memory Settings
    conversation_ttl_seconds: int = 1800  # 30 minutes (1800 seconds)
    max_conversation_turns: int = 3  # Remember last N Q&A pairs

     
    def validate(self):
        """Validate all configuration"""
        errors = []
        
        # Validate API keys (CRITICAL for production)
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY missing")
        
        if not self.pinecone_api_key:
            errors.append("PINECONE_API_KEY missing")
        
        if not self.pinecone_index_name:
            errors.append("PINECONE_INDEX_NAME missing")
        
        # Redis validation
        if not self.redis_host:
            errors.append("REDIS_HOST missing")
        
        if not self.redis_password:
            errors.append("REDIS_PASSWORD missing")
        
        # Supabase validation
        if not self.supabase_url:
            errors.append("SUPABASE_URL missing")
        
        if not self.supabase_service_role_key:
            errors.append("SUPABASE_SERVICE_ROLE_KEY missing")
        
        if errors:
            error_msg = "Config errors:\n" + "\n".join(errors)
            raise ValueError(error_msg)

    def display(self):
        print("\n Config:")
        print(f"  Data dir: {self.data_dir}")
        print(f"  Embedding model: {self.embedding_model}")
        print(f"  Chunk size: {self.chunk_size}")
        print(f"  Chunk overlap: {self.chunk_overlap}")
        print(f"  Pinecone index: {self.pinecone_index_name}")
        print(f"  Namespace: {self.pinecone_namespace}")
        print(f"  Query top-k: {self.query_top_k}")
        print(f"  LLM model: {self.llm_model}")


    def get_logging_config(self) -> dict:
        """
        Get configuration parameters for logging.
        Used to track which settings were used for each query.
        
        Returns:
            Dictionary with configuration values
        """
        return {
            "config_top_k": self.query_top_k,
            "config_chunk_size": self.chunk_size,
            "config_chunk_overlap": self.chunk_overlap,
            "config_similarity_threshold": self.query_similarity_threshold,
            "config_temperature": self.llm_temperature,
            "config_max_tokens": self.llm_max_tokens,
            "config_embedding_model": self.embedding_model,
        }

def get_config() -> Config:
    config = Config()
    config.validate()
    return config