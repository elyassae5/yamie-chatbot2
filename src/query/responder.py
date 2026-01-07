"""
Responder module - handles LLM integration for answer generation.
Calls OpenAI GPT-4o to generate answers based on retrieved context with
comprehensive logging and error handling.
"""

import structlog
import logging
from typing import Optional
from datetime import datetime
import openai

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from src.config import Config, get_config
from src.query.models import RetrievedChunk, QueryResponse
from src.query.prompts import PromptBuilder

logger = structlog.get_logger(__name__)


class Responder:
    """
    Handles LLM calls to generate answers from retrieved context.
    
    Responsibilities:
    - Build prompts from retrieved chunks
    - Call OpenAI API for answer generation
    - Handle errors and retries
    - Track response time and token usage
    """
    
    def __init__(self, config: Config = None):
        """
        Initialize the responder.
        
        Args:
            config: Optional configuration object (uses default if not provided)
        """
        self.config = config or get_config()
        
        # Set OpenAI API key
        openai.api_key = self.config.openai_api_key
        
        logger.info(
            "responder_initialized",
            model=self.config.llm_model,
            temperature=self.config.llm_temperature,
            max_tokens=self.config.llm_max_tokens
        )
    

    @retry(
        stop=stop_after_attempt(3),  # Try up to 3 times
        wait=wait_exponential(multiplier=1, min=2, max=10),  # Wait 2s, 4s, 8s
        retry=retry_if_exception_type((
            openai.APIError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.APITimeoutError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _call_openai_with_retry(self, messages: list, model: str, temperature: float, max_tokens: int):
        """
        Call OpenAI API with automatic retry on transient failures.
        
        Retry strategy:
        - Up to 3 attempts total
        - Exponential backoff: 2s, 4s, 8s between retries
        - Only retry on: Network errors, timeouts, rate limits
        - Don't retry on: Authentication errors, invalid requests
        
        Args:
            messages: Chat messages for the API
            model: Model name (e.g., "gpt-4o-mini")
            temperature: Temperature setting
            max_tokens: Max tokens in response
            
        Returns:
            OpenAI API response object
            
        Raises:
            openai.APIError: If all retries fail
        """
        logger.debug(
            "openai_api_call_attempt",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        response = openai.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        logger.debug("openai_api_call_successful")
        
        return response

    def generate_answer(
            self, 
            question: str, 
            chunks: list[RetrievedChunk],
            conversation_history: str = ""
        ) -> QueryResponse:
        """
        Generate an answer using retrieved chunks and LLM.
        
        Process:
        1. Build system and user prompts
        2. Call OpenAI API
        3. Extract and validate answer
        4. Track metrics (time, tokens)
        5. Handle errors gracefully
        
        Args:
            question: User's question
            chunks: Retrieved context chunks
            conversation_history: Optional conversation context
            
        Returns:
            QueryResponse with answer, sources, and metadata
        """
        start_time = datetime.utcnow()
        
        logger.info(
            "answer_generation_started",
            chunks_count=len(chunks),
            has_conversation_history=bool(conversation_history)
        )
        logger.debug("generation_question", question=question)
        
        # Build prompts
        try:
            system_prompt, user_prompt = PromptBuilder.build_complete_prompt(
                question, 
                chunks, 
                conversation_history
            )
            logger.debug(
                "prompts_built",
                system_prompt_length=len(system_prompt),
                user_prompt_length=len(user_prompt)
            )
        except Exception as e:
            logger.error(
                "prompt_building_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            return self._create_error_response(
                question=question,
                chunks=chunks,
                error_message=f"Prompt building failed: {str(e)}",
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )
        
        # Call OpenAI API
        try:
            logger.debug("openai_api_call_started")
            
            response = self._call_openai_with_retry(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.config.llm_model,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens
            )
            
            # Extract answer from response
            answer = response.choices[0].message.content.strip()
            
            # Log token usage
            if hasattr(response, 'usage') and response.usage:
                logger.info(
                    "token_usage",
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                    model=self.config.llm_model
                )
            
            # Determine if we actually got an answer or a "don't know" response
            has_answer = self._has_valid_answer(answer)
            
            # Calculate response time
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                "answer_generated",
                response_time_seconds=round(response_time, 2),
                answer_length=len(answer),
                has_answer=has_answer
            )
            
            return QueryResponse(
                question=question,
                answer=answer,
                sources=chunks,
                has_answer=has_answer,
                response_time_seconds=response_time,
            )
            
        except openai.APIError as e:
            logger.error(
                "openai_api_error",
                error=str(e),
                error_type="APIError"
            )
            return self._create_error_response(
                question=question,
                chunks=chunks,
                error_message=f"API error: {str(e)}",
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )
        
        except openai.RateLimitError as e:
            logger.warning(
                "openai_rate_limit_exceeded",
                error=str(e)
            )
            return self._create_error_response(
                question=question,
                chunks=chunks,
                error_message="Rate limit exceeded. Please try again in a moment.",
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )
        
        except openai.AuthenticationError as e:
            logger.error(
                "openai_authentication_error",
                error=str(e)
            )
            return self._create_error_response(
                question=question,
                chunks=chunks,
                error_message="Authentication failed. Please check API key.",
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )
        
        except openai.APIConnectionError as e:
            logger.error(
                "openai_connection_error",
                error=str(e)
            )
            return self._create_error_response(
                question=question,
                chunks=chunks,
                error_message="Could not connect to OpenAI. Please check your internet connection.",
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )
        
        except Exception as e:
            logger.error(
                "answer_generation_unexpected_error",
                error=str(e),
                error_type=type(e).__name__
            )
            return self._create_error_response(
                question=question,
                chunks=chunks,
                error_message=f"Unexpected error: {str(e)}",
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    def _has_valid_answer(self, answer: str) -> bool:
        """
        Check if the LLM provided a real answer or said "I don't know".
        
        Looks for common phrases that indicate the bot couldn't answer
        the question from the provided context.
        
        Args:
            answer: Generated answer text
            
        Returns:
            True if valid answer, False if "don't know" response
        """
        # Phrases that indicate "I don't know" responses (English + Dutch)
        dont_know_phrases = [
            "i don't have that information",
            "ik heb die informatie niet",
            "i don't have information",
            "ik heb geen informatie",
            "not found in the documents",
            "niet in de documenten",
            "cannot find",
            "kan niet vinden",
            "no information about",
            "geen informatie over",
            "not available in",
            "niet beschikbaar in",
            "don't see any information",
            "zie geen informatie",
        ]
        
        answer_lower = answer.lower()
        
        # Check if answer contains any "don't know" phrases
        for phrase in dont_know_phrases:
            if phrase in answer_lower:
                logger.debug(
                    "dont_know_phrase_detected",
                    phrase=phrase
                )
                return False
        
        logger.debug("answer_validated", has_information=True)
        return True
    
    def _create_error_response(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        error_message: str,
        response_time: float
    ) -> QueryResponse:
        """
        Create an error response when LLM call fails.
        
        This ensures the system fails gracefully and returns a structured
        response even when something goes wrong.
        
        Args:
            question: Original question
            chunks: Retrieved chunks (may be empty)
            error_message: Error description for user
            response_time: Time elapsed before error
            
        Returns:
            QueryResponse with error message and metadata
        """
        logger.error(
            "error_response_created",
            error_message=error_message,
            response_time_seconds=round(response_time, 2)
        )
        
        # User-friendly error message
        user_message = (
            "Sorry, I encountered an error while processing your question. "
            "Please try again in a moment."
        )
        
        return QueryResponse(
            question=question,
            answer=user_message,
            sources=chunks,
            has_answer=False,
            response_time_seconds=response_time,
        )
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimate the cost of an API call based on token usage.
        Useful for monitoring and budgeting.
        
        Args:
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion
            
        Returns:
            Estimated cost in USD
            
        Note:
            Pricing as of Dec 2024:
            GPT-4o: $2.50 per 1M input tokens, $10.00 per 1M output tokens
            GPT-4o-mini: $0.15 per 1M input tokens, $0.60 per 1M output tokens
        """
        # Pricing per 1M tokens (as of Dec 2024)
        if "mini" in self.config.llm_model.lower():
            input_cost_per_1m = 0.15
            output_cost_per_1m = 0.60
        else:  # GPT-4o
            input_cost_per_1m = 2.50
            output_cost_per_1m = 10.00
        
        input_cost = (prompt_tokens / 1_000_000) * input_cost_per_1m
        output_cost = (completion_tokens / 1_000_000) * output_cost_per_1m
        
        total_cost = input_cost + output_cost
        
        logger.debug(
            "cost_estimated",
            total_cost_usd=round(total_cost, 6),
            input_cost_usd=round(input_cost, 6),
            output_cost_usd=round(output_cost, 6),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=self.config.llm_model
        )
        
        return total_cost