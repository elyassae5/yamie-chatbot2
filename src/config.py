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
    query_top_k: int = 7                  # Number of chunks to retrieve
    query_similarity_threshold: float = 0.0
    
    # LLM Settings
    llm_model: str = "gpt-4o"               # OpenAI model for generation
    llm_temperature: float = 0.2            # Low = more factual, high = more creative
    llm_max_tokens: int = 600               # Max response length

     
    def validate(self):
        errors = []

        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY missing")

        if not self.pinecone_api_key:
            errors.append("PINECONE_API_KEY missing")

        if not Path(self.data_dir).exists():
            errors.append(f"Data directory not found: {self.data_dir}")

        if errors:
            raise ValueError("Config errors:\n" + "\n".join(errors))

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


def get_config() -> Config:
    config = Config()
    config.validate()
    return config
