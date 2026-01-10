"""
WhatsApp Webhook - Handles incoming WhatsApp messages via Twilio
"""

from fastapi import APIRouter, Request, HTTPException
import structlog
import os
from twilio.twiml.messaging_response import MessagingResponse

from src.query import QueryEngine
from src.config import get_config

logger = structlog.get_logger(__name__)
router = APIRouter()

# Initialize QueryEngine (singleton - reused across requests)
logger.info("query_engine_initialization_started")
try:
    engine = QueryEngine(config=get_config())
    logger.info("query_engine_initialized", status="success")
except Exception as e:
    logger.error(
        "query_engine_initialization_failed",
        error=str(e),
        error_type=type(e).__name__
    )
    engine = None


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Receive incoming WhatsApp messages from Twilio.
    
    When a user sends a WhatsApp message to your Twilio number,
    Twilio forwards it here as a POST request.
    
    We then:
    1. Extract the message and sender's phone number
    2. Process the question using QueryEngine
    3. Send the answer back via Twilio
    """
    
    # Check if engine is initialized
    if engine is None:
        logger.error("webhook_rejected", reason="engine_not_initialized")
        return MessagingResponse()  # Empty response (no message sent)
    
    try:
        # Get form data from Twilio
        form_data = await request.form()
        
        # Extract message details
        from_number = form_data.get("From", "")  # e.g., "whatsapp:+31612345678"
        incoming_message = form_data.get("Body", "").strip()
        
        logger.info(
            "whatsapp_message_received",
            from_number=from_number[:18] + "***",  # Mask for privacy
            message_length=len(incoming_message)
        )

        
        # Validate message
        if not incoming_message:
            logger.warning("empty_message_received", from_number=from_number[:15] + "***")
            response = MessagingResponse()
            response.message("Hallo! Stel me een vraag over Yamie PastaBar.")
            return str(response)
        
        # Process question using QueryEngine
        logger.info("processing_query", from_number=from_number[:15] + "***")
        
        query_response = engine.query(
            question=incoming_message,
            user_id=from_number,  # Use phone number as user_id for conversation memory
            top_k=7
        )
        
        # Format answer for WhatsApp (max 2200 chars to be safe)
        answer = query_response.answer
        if len(answer) > 2200:
            answer = answer[:2200] + "\n\n[Antwoord ingekort - vraag voor meer details]"
        
        logger.info(
            "query_processed",
            from_number=from_number[:18] + "***",
            has_answer=query_response.has_answer,
            answer_length=len(answer)
        )
        
        # ========== ADD SUPABASE LOGGING  ==========
        try:
            from src.database import get_supabase_logger
            from src.query.system_prompt import ACTIVE_SYSTEM_PROMPT_VERSION
            from src.config import get_config
            
            supabase_logger = get_supabase_logger()
            config = get_config()
            
            supabase_logger.log_query(
                user_id=from_number,  # WhatsApp number as user_id
                question=incoming_message,
                answer=answer,
                has_answer=query_response.has_answer,
                response_time_seconds=query_response.response_time_seconds,
                sources=[
                    {
                        "source": chunk.source,
                        "category": chunk.category,
                        "similarity_score": chunk.similarity_score,
                    }
                    for chunk in query_response.sources
                ],
                chunks_retrieved=len(query_response.sources),
                client_ip="whatsapp_webhook",  # Indicate it came from WhatsApp
                model=config.llm_model,
                config_top_k=7,
                config_chunk_size=config.chunk_size,
                config_chunk_overlap=config.chunk_overlap,
                config_similarity_threshold=config.query_similarity_threshold,
                config_temperature=config.llm_temperature,
                config_max_tokens=config.llm_max_tokens,
                config_embedding_model=config.embedding_model,
                system_prompt_version=ACTIVE_SYSTEM_PROMPT_VERSION,
            )
            
            logger.info("whatsapp_query_logged_to_supabase", from_number=from_number[:15] + "***")
            
        except Exception as e:
            # Don't crash if logging fails
            logger.error(
                "supabase_logging_failed_in_webhook",
                error=str(e),
                error_type=type(e).__name__
            )
        # ========== END SUPABASE LOGGING ==========

        # Create Twilio response
        from fastapi.responses import Response as FastAPIResponse

        response = MessagingResponse()
        response.message(answer)

        # Return with explicit XML content type
        return FastAPIResponse(
            content=str(response),
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(
            "webhook_processing_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        
        # Send error message to user
        response = MessagingResponse()
        response.message("Sorry, er is een fout opgetreden. Probeer het later opnieuw.")
        return str(response)