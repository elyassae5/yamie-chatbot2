"""
Query engine - main orchestrator for the question-answering system.
Ties together retrieval, prompt building, and answer generation.
"""

from typing import Optional

from src.config import Config, get_config
from src.query.models import QueryRequest, QueryResponse
from src.query.retriever import Retriever
from src.query.responder import Responder


class QueryEngine:
    """
    Main query engine that orchestrates the RAG pipeline.
    This is the public API for asking questions.
    """
    
    def __init__(self, config: Config = None):
        """
        Initialize the query engine with retriever and responder.
        
        Args:
            config: Optional configuration object
        """
        self.config = config or get_config()
        
        print("\n" + "="*80)
        print("🚀 Initializing YamieBot Query Engine")
        print("="*80)
        
        # Initialize components
        self.retriever = Retriever(config=self.config)
        self.responder = Responder(config=self.config)
        
        print("="*80)
        print("✅ Query Engine ready!")
        print("="*80 + "\n")
    
    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        category_filter: Optional[str] = None,
    ) -> QueryResponse:
        """
        Answer a question using the RAG pipeline.
        
        This is the main entry point for querying the system.
         
        Args:
            question: User's question (in Dutch or English)
            top_k: Number of chunks to retrieve (default from config)
            category_filter: Optional category to search in ("menu", "sop", "hr", "equipment")
            
        Returns:
            QueryResponse with answer, sources, and metadata
            
        Example:
            >>> engine = QueryEngine()
            >>> response = engine.query("Wat voor pizza's hebben we?")
            >>> print(response.answer)
            "We hebben Margherita, Carbonara, en Diavola pizza's..."
        """
        # Create request object
        request = QueryRequest(
            question=question,
            top_k=top_k or self.config.query_top_k,
            category_filter=category_filter,
        )
        
        # Validate request
        try:
            request.validate()
        except ValueError as e:
            print(f"❌ Invalid request: {e}")
            raise
        
        print("\n" + "="*80)
        print(f"📝 Processing question: '{question}'")
        print("="*80)
        
        # Step 1: Retrieve relevant chunks
        chunks = self.retriever.retrieve(request)
        
        if not chunks:
            print("⚠️  No relevant chunks found - answering with 'don't know'")
            return QueryResponse(
                question=question,
                answer="Ik heb die informatie niet in de bedrijfsdocumenten. (I don't have that information in the company documents.)",
                sources=[],
                has_answer=False,
                response_time_seconds=0.0,
            )
        
        # Step 2: Generate answer using LLM
        response = self.responder.generate_answer(
            question=question,
            chunks=chunks,
        )
        
        print("="*80)
        print(f"✅ Query completed ")
        print("="*80 + "\n")
        
        return response
    
    def get_stats(self) -> dict:
        """
        Get statistics about the query engine.
        
        Returns:
            Dictionary with system stats
        """
        retriever_stats = self.retriever.get_stats()
        
        return {
            "retriever": retriever_stats,
            "config": {
                "top_k": self.config.query_top_k,
                "llm_model": self.config.llm_model,
                "temperature": self.config.llm_temperature,
                "max_tokens": self.config.llm_max_tokens,
            }
        }