"""
Query Route - Main endpoint for asking questions

POST /api/query
GET /api/stats
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging

from backend.models import QueryRequest, QueryResponse, ErrorResponse, Source
from src.query import QueryEngine
from src.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize QueryEngine (singleton - reused across requests)
logger.info("Initializing QueryEngine...")
try:
    engine = QueryEngine(config=get_config())
    logger.info("✓ QueryEngine initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize QueryEngine: {e}", exc_info=True)
    engine = None


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        200: {"description": "Query processed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Server error"},
    }
)
async def query(request: QueryRequest) -> QueryResponse:
    """
    Process a question and return an answer.
    
    This endpoint:
    1. Validates the input
    2. Checks conversation memory (Redis)
    3. Searches relevant documents (Pinecone)
    4. Generates answer (OpenAI GPT-4o-mini)
    5. Returns structured response
    
    **Example Request:**
```json
    {
        "question": "Wie is Daoud?",
        "user_id": "gradio_user",
        "debug": true
    }
```
    
    **Example Response:**
```json
    {
        "question": "Wie is Daoud?",
        "answer": "Daoud is verantwoordelijk voor...",
        "sources": [...],
        "has_answer": true,
        "response_time_seconds": 1.23,
        "debug_info": {
            "transformed_question": "Wie is Daoud en wat zijn zijn taken?",
            "chunks_retrieved": 7,
            "top_chunks": [...]
        }
    }
```
    """
    
    # Check if engine is initialized
    if engine is None:
        logger.error("QueryEngine not initialized")
        raise HTTPException(
            status_code=500,
            detail="Query engine not initialized. Check server logs."
        )
    
    # Log incoming request
    logger.info(f"Query received from user: {request.user_id}")
    logger.debug(f"Question: {request.question}")
    if request.debug:
        logger.info("Debug mode enabled")
    
    start_time = datetime.utcnow()
    
    try:
        # Store original question for debug info
        original_question = request.question
        
        # Process query using QueryEngine
        response = engine.query(
            question=request.question,
            user_id=request.user_id,
            top_k=request.top_k,
        )
        
        # Build debug info if requested
        debug_info = None
        if request.debug:
            debug_info = {
                "original_question": original_question,
                "transformed_question": response.question if response.question != original_question else None,
                "chunks_retrieved": len(response.sources),
                "top_chunks": [
                    {
                        "source": chunk.source,
                        "category": chunk.category,
                        "score": round(chunk.similarity_score, 3),
                        "text_preview": chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text
                    }
                    for chunk in response.sources[:3]  # Top 3 chunks
                ],
                "all_sources": [
                    {
                        "source": chunk.source,
                        "score": round(chunk.similarity_score, 3)
                    }
                    for chunk in response.sources
                ]
            }
            logger.debug(f"Debug info: {debug_info}")
        
        # Convert to API response model
        api_response = QueryResponse(
            question=response.question,
            answer=response.answer,
            sources=[
                Source(
                    source=chunk.source,
                    category=chunk.category,
                    similarity_score=chunk.similarity_score,
                    text=chunk.text if hasattr(chunk, 'text') else None
                )
                for chunk in response.sources
            ],
            has_answer=response.has_answer,
            response_time_seconds=response.response_time_seconds,
            user_id=request.user_id,
            timestamp=datetime.utcnow(),
            debug_info=debug_info  # ← Include debug info!
        )
        
        logger.info(f"✓ Query processed in {response.response_time_seconds:.2f}s")
        logger.debug(f"Has answer: {response.has_answer}, Sources: {len(response.sources)}")
        
        # TODO: Log to Supabase here (Phase 3)
        
        return api_response
        
    except ValueError as e:
        # Invalid input (e.g., empty question)
        logger.warning(f"Invalid query: {e}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Unexpected error
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )


@router.get("/stats")
async def get_stats():
    """
    Get query engine statistics.
    
    Returns information about the system:
    - Vector store stats (total documents, namespace, etc.)
    - Configuration settings
    - Memory stats
    """
    
    if engine is None:
        raise HTTPException(status_code=500, detail="Query engine not initialized")
    
    try:
        stats = engine.get_stats()
        return {
            "status": "ok",
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))