"""
Responder module - handles LLM integration for answer generation.
Calls OpenAI GPT-4 to generate answers based on retrieved context.
"""

from typing import Optional
from datetime import datetime
import openai

from src.config import Config, get_config
from src.query.models import RetrievedChunk, QueryResponse
from src.query.prompts import PromptBuilder


class Responder:
    """
    Handles LLM calls to generate answers from retrieved context.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or get_config()
        
        # Set OpenAI API key
        openai.api_key = self.config.openai_api_key
        
        print(f"✅ Responder initialized with model: {self.config.llm_model}")
    
    def generate_answer(self, question: str, chunks: list[RetrievedChunk]) -> QueryResponse:
        """
        Generate an answer using retrieved chunks and LLM.
        
        Args:
            question: User's question
            chunks: Retrieved context chunks
            
        Returns:
            QueryResponse with answer, sources, and metadata
        """
        start_time = datetime.utcnow()
        
        # Calculate confidence before attempting to answer
        confidence = PromptBuilder.calculate_confidence(chunks)
        
        print(f"\n💬 Generating answer for: '{question}'")
        print(f"   Confidence: {confidence}")
        print(f"   Retrieved chunks: {len(chunks)}")
        
        # Build prompts
        system_prompt, user_prompt = PromptBuilder.build_complete_prompt(question, chunks)
        
        try:
            # Call OpenAI API
            response = openai.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
            )
            
            # Extract answer from response
            answer = response.choices[0].message.content.strip()
            
            # Determine if we actually got an answer or a "don't know" response
            has_answer = self._has_valid_answer(answer)
            
            # Calculate response time
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            print(f"✅ Answer generated in {response_time:.2f}s")
            
            return QueryResponse(
                question=question,
                answer=answer,
                sources=chunks,
                has_answer=has_answer,
                confidence=confidence,
                response_time_seconds=response_time,
            )
            
        except openai.APIError as e:
            print(f"❌ OpenAI API error: {e}")
            return self._create_error_response(
                question=question,
                chunks=chunks,
                error_message=f"API error: {str(e)}",
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )
        
        except openai.RateLimitError as e:
            print(f"❌ Rate limit exceeded: {e}")
            return self._create_error_response(
                question=question,
                chunks=chunks,
                error_message="Rate limit exceeded. Please try again in a moment.",
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )
        
        except Exception as e:
            print(f"❌ Unexpected error generating answer: {e}")
            return self._create_error_response(
                question=question,
                chunks=chunks,
                error_message=f"Unexpected error: {str(e)}",
                response_time=(datetime.utcnow() - start_time).total_seconds()
            )
    
    def _has_valid_answer(self, answer: str) -> bool:
        """
        Check if the LLM provided a real answer or said "I don't know".
        
        Args:
            answer: Generated answer text
            
        Returns:
            True if valid answer, False if "don't know" response
        """
        # Phrases that indicate "I don't know" responses
        dont_know_phrases = [
            "i don't have that information",
            "ik heb die informatie niet",
            "not found in the documents",
            "niet in de documenten",
            "cannot find",
            "kan niet vinden",
            "no information about",
            "geen informatie over",
        ]
        
        answer_lower = answer.lower()
        
        # Check if answer contains any "don't know" phrases
        for phrase in dont_know_phrases:
            if phrase in answer_lower:
                return False
        
        
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
        
        Args:
            question: Original question
            chunks: Retrieved chunks
            error_message: Error description
            response_time: Time elapsed
            
        Returns:
            QueryResponse with error message
        """
        return QueryResponse(
            question=question,
            answer=f"Sorry, I encountered an error: {error_message}",
            sources=chunks,
            has_answer=False,
            confidence="low",
            response_time_seconds=response_time,
        )