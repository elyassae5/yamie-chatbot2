"""
Prompt templates and construction for the query system.
Handles context formatting and grounding rules.

The system prompt is now in a separate file (system_prompt.py) for easy editing!
"""

from typing import List
from src.query.models import RetrievedChunk
from src.query.system_prompt import (
    ACTIVE_SYSTEM_PROMPT as SYSTEM_PROMPT,
    ACTIVE_SYSTEM_PROMPT_VERSION as SYSTEM_PROMPT_VERSION
)

class PromptBuilder:
    """
    Constructs prompts for the LLM with retrieved context.
    Ensures answers are grounded in provided documents.
    
    Note: The system prompt is imported from system_prompt.py
    Edit that file to change the bot's behavior!
    """
    
    @staticmethod
    def build_context(chunks: List[RetrievedChunk]) -> str:
        """
        Format retrieved chunks into a context string for the LLM.
        
        Args:
            chunks: List of retrieved chunks, sorted by relevance
            
        Returns:
            Formatted context string
        """
        if not chunks:
            return "No relevant documents found."
        
        context_parts = ["Here are the potentially relevant excerpts from company documents that may contain the answer, read them thoroughly and answer intelligently:\n"]
        
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(f"Source: {chunk.source}")
            context_parts.append(f"Category: {chunk.category}")
            context_parts.append(f"Relevance: {chunk.similarity_score:.2f}")
            context_parts.append(f"\nContent:\n{chunk.text}")
            context_parts.append("-" * 80)
        
        return "\n".join(context_parts)
    
    @staticmethod
    def build_user_prompt(question: str, context: str, conversation_history: str = "") -> str:
        """
        Construct the user prompt with context and question.
        
        Args:
            question: User's question
            context: Formatted context from retrieved chunks
            conversation_history: Optional conversation history for context
            
        Returns:
            Complete user prompt
        """
        prompt_parts = []
        
        # Add conversation history if available
        if conversation_history:
            prompt_parts.append("\n" + "="*80 + "\n")
            prompt_parts.append("CONVERSATION HISTORY (for context only):\n")
            prompt_parts.append("="*80 + "\n")
            prompt_parts.append(conversation_history)
            prompt_parts.append("\n" + "="*80 + "\n\n")
        
        # Add document context
        prompt_parts.append("="*80 + "\n")
        prompt_parts.append("DOCUMENT EXCERPTS - YOUR ONLY SOURCE OF TRUTH:\n")
        prompt_parts.append("(Use ONLY information from these documents!)\n")
        prompt_parts.append("="*80 + "\n")
        prompt_parts.append(context)
        prompt_parts.append("\n" + "="*80 + "\n\n")
        
        # Add question
        prompt_parts.append("QUESTION:\n")
        prompt_parts.append(f"{question}\n\n")
        prompt_parts.append("Answer (using ONLY the document excerpts above):\n")
        
        return "".join(prompt_parts)
    
    @staticmethod
    def build_complete_prompt(
        question: str, 
        chunks: List[RetrievedChunk],
        conversation_history: str = ""
    ) -> tuple[str, str]:
        """
        Build the complete prompt with system message and user message.
        
        Args:
            question: User's question
            chunks: Retrieved context chunks
            conversation_history: Optional conversation history
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        context = PromptBuilder.build_context(chunks)
        user_prompt = PromptBuilder.build_user_prompt(question, context, conversation_history)
        
        return (SYSTEM_PROMPT, user_prompt)