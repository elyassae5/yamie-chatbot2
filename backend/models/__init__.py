"""
API Models - Request/Response schemas

Pydantic models for FastAPI validation and documentation.
These define the CONTRACT between frontend and backend.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class QueryRequest(BaseModel):
    """
    Request model for /api/query endpoint.
    This is what Gradio/WhatsApp sends to the backend.
    """
    
    question: str = Field(
        ..., 
        min_length=1, 
        max_length=500,
        description="User's question (in Dutch or English)",
        examples=["Wie is Daoud?", "What are the sick leave policies?"]
    )
    
    user_id: str = Field(
        default="anonymous",
        description="User identifier (session ID, phone number, etc.)",
        examples=["gradio_user", "+31612345678", "session_abc123"]
    )
    
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of document chunks to retrieve (default from config)"
    )

    debug: bool = Field(
        default=False,
        description="Enable debug mode to see retrieved chunks and transformations"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Wie is Daoud en wat doet hij?",
                "user_id": "gradio_user",
                "top_k": 7,
                "debug": False
            }
        }


class Source(BaseModel):
    """Source document information."""
    
    source: str = Field(..., description="Source document filename")
    category: str = Field(default="general", description="Document category")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    text: Optional[str] = Field(None, description="Chunk text (only for debugging)")


class QueryResponse(BaseModel):
    """
    Response model for /api/query endpoint.
    This is what the backend sends back to Gradio/WhatsApp.
    """
    
    question: str = Field(..., description="Original question asked")
    answer: str = Field(..., description="Generated answer")
    sources: List[Source] = Field(default=[], description="Source documents used")
    has_answer: bool = Field(..., description="Whether a valid answer was found")
    response_time_seconds: float = Field(..., description="Time taken to process query")
    user_id: str = Field(..., description="User who asked the question")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the query was processed")
    
    debug_info: Optional[dict] = Field(
        default=None,
        description="Debug information (only if debug=True in request)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Wie is Daoud?",
                "answer": "Daoud is verantwoordelijk voor managementondersteuning...",
                "sources": [
                    {
                        "source": "manual.docx",
                        "category": "hr",
                        "similarity_score": 0.89
                    }
                ],
                "has_answer": True,
                "response_time_seconds": 1.23,
                "user_id": "gradio_user",
                "timestamp": "2026-01-02T16:30:00Z",
                 "debug_info": None
            }
        }


class HealthResponse(BaseModel):
    """
    Response model for /api/health endpoint.
    Used to check if the system is working properly.
    """
    
    status: str = Field(..., description="Health status", examples=["healthy", "unhealthy"])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="Backend version")
    components: dict = Field(default={}, description="Component health status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2026-01-02T16:30:00Z",
                "version": "1.0.0",
                "components": {
                    "query_engine": "healthy",
                    "redis": "healthy",
                    "pinecone": "healthy"
                }
            }
        }


class ErrorResponse(BaseModel):
    """
    Response model for errors.
    Sent when something goes wrong.
    """
    
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Query processing failed",
                "detail": "Pinecone index not found",
                "timestamp": "2026-01-02T16:30:00Z"
            }
        }