import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    data_dir: str = "./data"
    supported_extensions: list[str] = field(default_factory=lambda: [".pdf"])

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072
    embedding_batch_size: int = 100

    # Pinecone
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY", "")
    pinecone_index_name: str = os.getenv("PINECONE_INDEX_NAME", "yamie-test")
    pinecone_namespace: str = "documents"

    # Chunking
    chunk_size: int = 1024
    chunk_overlap: int = 250
     
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


def get_config() -> Config:
    config = Config()
    config.validate()
    return config
