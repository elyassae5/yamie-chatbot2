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
    # Bilingual (Dutch/English) for Yamie PastaBar staff
    SYSTEM_PROMPT = """Je bent een interne assistent voor Yamie PastaBar medewerkers in Nederland.

Jouw rol:
- Beantwoord vragen ALLEEN op basis van de verstrekte bedrijfsdocumenten
- Wees behulpzaam, duidelijk en beknopt
- Gebruik een professionele maar vriendelijke toon
- Antwoord in dezelfde taal als de vraag (Nederlands of Engels)

Cruciale regels:
- Verzin NOOIT informatie
- Gebruik NOOIT kennis buiten de verstrekte context
- Als het antwoord niet in de documenten staat, zeg dan: "Ik heb die informatie niet in de bedrijfsdocumenten."
- Vermeld altijd uit welk document je antwoord komt
- Als meerdere documenten relevante informatie bevatten, noem dan alle bronnen

Onthoud: Medewerkers vertrouwen op jou voor accurate bedrijfsinformatie. Bij twijfel, zeg dat je het niet weet in plaats van te raden.

---

You are an internal assistant for Yamie PastaBar staff in the Netherlands.

Your role:
- Answer questions ONLY based on the provided company documents
- Be helpful, clear, and concise
- Use a professional but friendly tone
- Answer in the same language as the question (Dutch or English)

Critical rules:
- NEVER make up information
- NEVER use knowledge outside the provided context
- If the answer is not in the documents, say: "I don't have that information in the company documents."
- Always cite which document your answer comes from
- If multiple documents contain relevant info, mention all sources

Remember: Staff rely on you for accurate company information. When in doubt, say you don't know rather than guessing."""

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
        
        context_parts = ["Here are relevant excerpts from company documents:\n"]
        
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(f"\n--- Document {i} ---")
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
- Cite which document(s) you used (mention the source filename)
- If the context doesn't contain enough information to answer, say: "I don't have that information in the company documents." (or in Dutch: "Ik heb die informatie niet in de bedrijfsdocumenten.")
- Be specific and helpful
- Answer in the same language as the question

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
    
    
    @staticmethod
    def calculate_confidence(chunks: List[RetrievedChunk]) -> str:
        """
        Calculate confidence level based on retrieval quality.
        Uses top-3 chunks to avoid being dragged down by irrelevant results.
        
        Args:
            chunks: Retrieved chunks with similarity scores (sorted by score, highest first)
            
        Returns:
            Confidence level: "high", "medium", or "low"
        """
        if not chunks:
            return "low"
        
        # Use top 3 chunks only (or fewer if less than 3 chunks retrieved)
        top_chunks = chunks[:3]
        
        # Calculate average similarity score of top chunks
        avg_score = sum(chunk.similarity_score for chunk in top_chunks) / len(top_chunks)
        
        # Also check the best individual chunk
        max_score = chunks[0].similarity_score if chunks else 0.0
        
        # Determine confidence
        # High: Top chunks average > 0.8 AND best chunk > 0.85
        if avg_score >= 0.8 and max_score >= 0.85:
            return "high"
        # Medium: Top chunks average > 0.6 OR best chunk > 0.75
        elif avg_score >= 0.6 or max_score >= 0.75:
            return "medium"
        else:
            return "low"


    @staticmethod
    def should_answer(chunks: List[RetrievedChunk], confidence_threshold: str = "low") -> bool:
        """
        Decide if we should attempt to answer based on retrieval quality.
        
        Args:
            chunks: Retrieved chunks
            confidence_threshold: Minimum confidence to answer ("low", "medium", "high")
            
        Returns:
            True if we should answer, False if we should say "I don't know"
        """
        if not chunks:
            return False
        
        confidence = PromptBuilder.calculate_confidence(chunks)
        
        threshold_map = {
            "low": ["low", "medium", "high"],
            "medium": ["medium", "high"],
            "high": ["high"]
        }
        
        return confidence in threshold_map.get(confidence_threshold, [])