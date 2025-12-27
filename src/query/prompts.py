"""
Prompt templates and construction for the query system.
Handles system prompts, context formatting, and grounding rules.
"""

from typing import List
from src.query.models import RetrievedChunk


class PromptBuilder:
    """
    Constructs prompts for the LLM with retrieved context.
    Ensures answers are grounded in provided documents.
    """
    
    # System prompt - defines the AI's role and constraints

    SYSTEM_PROMPT = """You are an internal assistant for Yamie PastaBar staff in the Netherlands.

Your role:
- Answer questions based ONLY on the provided company documents
- Be helpful, clear, and conversational
- If the documents contain RELATED information, use it to answer - even if not exact

Critical rules:
- NEVER make up information
- NEVER use knowledge outside the provided context
- If the answer is in the documents, provide it clearly
- If the documents mention something SIMILAR to what's asked, explain what you found
- Always cite which document your answer comes from
- Only say "I don't have that information" if the documents are completely unrelated

Examples of good answers:

Question: "How many sick days do I have?"
Good: "According to the HR policy, you have 10 sick days per year. (Source: hr_policy.pdf)"

Question: "Are schedules posted 18 days in advance?"
Good: "According to the HR policy, schedules are posted 2 weeks (14 days) in advance. I don't see a specific mention of 18 days. (Source: hr_policy.pdf)"

Question: "What pizzas do you have?"
Good: "I don't have information about pizzas in the company documents."

Be smart: Use related information when it helps answer the question!
Remember: If the documents contain relevant information, use it! Don't be overly strict about exact wording.
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
    def build_user_prompt(question: str, context: str) -> str:
        """
        Construct the user prompt with context and question.
        
        Args:
            question: User's question
            context: Formatted context from retrieved chunks
            
        Returns:
            Complete user prompt
        """
        return f"""{context}

Question: {question}

Instructions:
- Answer the question using ONLY the information provided above
- Always cite sources by their filename (e.g., "According to sop_operations.pdf...")
- If the context doesn't contain enough information to answer, indicate so appropriately
- Be specific and helpful
- Answer in the same language as the question (if question is in english, you must provide the answer in English and not in any
other language. if it's in dutch, you must give the answer in Dutch)
Answer:"""
    
    @staticmethod
    def build_complete_prompt(question: str, chunks: List[RetrievedChunk]) -> tuple[str, str]:
        """
        Build the complete prompt with system message and user message.
        
        Args:
            question: User's question
            chunks: Retrieved context chunks
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        context = PromptBuilder.build_context(chunks)
        user_prompt = PromptBuilder.build_user_prompt(question, context)
        
        return (PromptBuilder.SYSTEM_PROMPT, user_prompt)