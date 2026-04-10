"""
Chat Route - Admin dashboard chat with YamieBot

POST /api/chat
Allows admins to chat with YamieBot directly from the dashboard.
Uses the same YamieAgent engine as the WhatsApp/API routes.
Requires JWT authentication.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import structlog

from admin_dashboard.backend.auth.jwt_handler import get_current_user_simple

logger = structlog.get_logger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    question: str


class ChatSource(BaseModel):
    source: str
    category: str
    similarity_score: float


class ChatResponse(BaseModel):
    question: str
    answer: str
    has_answer: bool
    response_time_seconds: float
    sources: list[ChatSource]


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    username: str = Depends(get_current_user_simple),
):
    """
    Send a message to YamieBot and get a response.

    Uses the same agent engine as WhatsApp. Conversation history is tracked
    per admin user in Redis (TTL 30 min, same as WhatsApp users).

    Requires JWT authentication.
    """
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Vraag mag niet leeg zijn")

    # Use admin_{username} as user_id to keep admin conversations
    # separate from WhatsApp users in Redis
    user_id = f"admin_{username}"

    logger.info("admin_chat_request", username=username, question=request.question[:100])

    try:
        from backend.engine import engine

        if engine is None:
            raise HTTPException(status_code=500, detail="Agent niet beschikbaar")

        response = engine.query(
            question=request.question.strip(),
            user_id=user_id,
        )

        logger.info(
            "admin_chat_response",
            username=username,
            has_answer=response.has_answer,
            response_time=round(response.response_time_seconds, 2),
        )

        return ChatResponse(
            question=response.question,
            answer=response.answer,
            has_answer=response.has_answer,
            response_time_seconds=response.response_time_seconds,
            sources=[
                ChatSource(
                    source=chunk.source,
                    category=chunk.category,
                    similarity_score=chunk.similarity_score,
                )
                for chunk in response.sources
            ],
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("admin_chat_failed", username=username, error=str(e), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="Er is een fout opgetreden. Probeer het opnieuw.")
