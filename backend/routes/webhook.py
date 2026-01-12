"""
WhatsApp Webhook - Handles incoming WhatsApp messages via Twilio
"""

from fastapi import APIRouter, Request, HTTPException
import structlog
import os
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

from src.query import QueryEngine
from src.config import get_config


def is_whitelisted(phone_number: str) -> bool:
    """
    Check if a phone number is whitelisted in Supabase.
    
    Args:
        phone_number: Phone number in format "whatsapp:+31684365220"
        
    Returns:
        True if whitelisted and active, False otherwise
    """
    try:
        from src.database import get_supabase_logger
        
        supabase_logger = get_supabase_logger()
        
        # Query Supabase for this phone number
        response = supabase_logger.client.table("whitelisted_numbers").select("*").eq("phone_number", phone_number).eq("is_active", True).execute()
        
        # Check if we got a result
        if response.data and len(response.data) > 0:
            logger.info(
                "whitelist_check_passed",
                phone_number=phone_number[:18] + "***",
                user_name=response.data[0].get("name", "Unknown")
            )
            return True
        else:
            logger.warning(
                "whitelist_check_failed",
                phone_number=phone_number[:18] + "***",
                reason="not_in_whitelist"
            )
            return False
            
    except Exception as e:
        logger.error(
            "whitelist_check_error",
            error=str(e),
            error_type=type(e).__name__,
            phone_number=phone_number[:18] + "***"
        )
        # Fail closed - if whitelist check fails, deny access
        return False



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

# Initialize Twilio client for sending typing indicators
try:
    twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    
    if twilio_account_sid and twilio_auth_token:
        twilio_client = Client(twilio_account_sid, twilio_auth_token)
        logger.info("twilio_client_initialized", status="success")
    else:
        twilio_client = None
        logger.warning("twilio_client_not_initialized", reason="missing_credentials")
except Exception as e:
    logger.error("twilio_client_initialization_failed", error=str(e))
    twilio_client = None


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

        # ========== WHITELIST CHECK ==========
        if not is_whitelisted(from_number):
            logger.warning(
                "unauthorized_access_attempt",
                from_number=from_number[:18] + "***",
                message=incoming_message[:70] + "..." if len(incoming_message) > 70 else incoming_message
            )
            
            response = MessagingResponse()
            response.message(
                "Sorry, je bent niet geautoriseerd om deze service te gebruiken. "
                "Neem contact op met je manager voor toegang."
            )
            
            from fastapi.responses import Response as FastAPIResponse
            return FastAPIResponse(
                content=str(response),
                media_type="application/xml"
            )
        # ========== END WHITELIST CHECK ==========


        # ========== SEND ACKNOWLEDGMENT MESSAGE ==========
        if twilio_client:
            try:
                # Get Twilio phone number from environment
                twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
                
                # Send acknowledgment
                twilio_client.messages.create(
                    from_=twilio_number,
                    to=from_number,
                    body="📄 Doorzoekt documenten..."  # "Searching for information..."
                )
                logger.debug("acknowledgment_sent", to=from_number[:18] + "***")
            except Exception as e:
                # Don't crash if acknowledgment fails
                logger.warning("acknowledgment_failed", error=str(e))
        # ========== END ACKNOWLEDGMENT MESSAGE ==========

        
        # Validate message
        if not incoming_message:
            logger.warning("empty_message_received", from_number=from_number[:15] + "***")
            response = MessagingResponse()
            response.message("Hallo! Stel me een vraag over Yamie PastaBar.")
            from fastapi.responses import Response as FastAPIResponse
            return FastAPIResponse(
                content=str(response),
                media_type="application/xml"
            )
        
        # ========== PROCESS QUERY WITH ERROR HANDLING ==========
        logger.info("processing_query", from_number=from_number[:15] + "***")
        
        try:
            # Process question using QueryEngine
            query_response = engine.query(
                question=incoming_message,
                user_id=from_number,  # Use phone number as user_id for conversation memory
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
            
            # ========== SUPABASE LOGGING ==========
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
            return FastAPIResponse(
                content=str(response),
                media_type="application/xml"
            )
        
        except ValueError as e:
            # Handle validation errors (like question too long)
            logger.warning(
                "invalid_question",
                error=str(e),
                from_number=from_number[:18] + "***"
            )
            
            from fastapi.responses import Response as FastAPIResponse
            response = MessagingResponse()
            
            if "too long" in str(e).lower():
                response.message(
                    "Sorry, je vraag is te lang (max 500 karakters). "
                    "Stel een kortere, specifieke vraag."
                )
            else:
                response.message(
                    "Sorry, er is iets misgegaan met je vraag. "
                    "Probeer het opnieuw."
                )
            
            return FastAPIResponse(
                content=str(response),
                media_type="application/xml"
            )
        # ========== END QUERY PROCESSING ==========
        
    except Exception as e:
        # Handle any other unexpected errors
        logger.error(
            "webhook_processing_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        
        # Send error message to user
        from fastapi.responses import Response as FastAPIResponse
        response = MessagingResponse()
        response.message("Sorry, er is een technische fout opgetreden. Probeer het later opnieuw.")
        return FastAPIResponse(
            content=str(response),
            media_type="application/xml"
        )