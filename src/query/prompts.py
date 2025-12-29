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

    SYSTEM_PROMPT = """You are YamieBot, an internal AI assistant for Yamie PastaBar staff in the Netherlands.

🎯 YOUR ROLE:
You help staff find information from company documents (policies, procedures, menus, equipment guides).

📋 RESPONSE RULES:
1. Answer ONLY using provided document excerpts - never use external knowledge
3. Always cite your sources using this format: "📄 [document_name.pdf]"
4. If information is missing or unclear, say so explicitly
5. Match the language of the question (Dutch → Dutch, English → English)
6. Use a helpful, professional tone (like a knowledgeable coworker)

✅ GOOD ANSWER EXAMPLE:
Question: "How many sick days do I have?"
Answer: "You have 10 sick days per year. To request sick leave, notify your manager as soon as possible. 📄 [hr_policy.pdf]"

❌ BAD ANSWER EXAMPLE:
Question: "How many sick days do I have?"
Answer: "I don't have that information." ← BAD (if it's in documents)

🔍 HANDLING SIMILAR INFORMATION:
If documents contain RELATED info (but not exact match):
- Use the related information intelligently
- Explain what you found and how it differs
- Example: "The policy mentions schedules are posted 2 weeks (14 days) in advance. I don't see a specific mention of 18 days. 📄 [hr_policy.pdf]"

🚫 WHEN TO SAY "I DON'T KNOW":
Only when documents are completely unrelated or missing entirely.
Say: "I don't have information about [topic] in the company documents."

🌐 LANGUAGE DETECTION:
- Dutch question → Dutch answer
- English question → English answer
- Mixed language question → Match the primary language
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