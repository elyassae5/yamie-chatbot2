"""
Redis-backed conversation memory for multi-turn conversations.


Stores conversation history with automatic expiration (TTL).
Each user (identified by phone number or session ID) gets their own conversation history.

Features:
- Automatic cleanup after inactivity (30 min default)
- Multi-user support
- Fast in-memory storage
- Persistent across server restarts
"""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime
import redis

from src.config import Config, get_config

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Manages conversation history using Redis.
    
    Each conversation is stored as a list of Q&A pairs with automatic expiration.
    """
    
    def __init__(self, config: Config = None):
        """
        Initialize Redis connection for conversation memory.
        
        Args:
            config: Configuration object (uses default if not provided)
        """
        self.config = config or get_config()
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Redis"""
        try:
            logger.info(f"Connecting to Redis at {self.config.redis_host}:{self.config.redis_port}")
            
            # Create Redis connection
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                password=self.config.redis_password if self.config.redis_password else None,
                db=self.config.redis_db,
                decode_responses=True,  # Automatically decode bytes to strings
                socket_connect_timeout=5,  # 5 second timeout
                socket_timeout=5,

            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("✓ Successfully connected to Redis")
            
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("Conversation memory will not work without Redis!")
            self.redis_client = None
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            self.redis_client = None
      
    def _get_key(self, user_id: str) -> str:
        """
        Generate Redis key for a user's conversation.
        
        Args:
            user_id: User identifier (phone number, session ID, etc.)
            
        Returns:
            Redis key string
        """
        return f"conversation:{user_id}"
    
    def add_turn(self, user_id: str, question: str, answer: str) -> bool:
        """
        Add a Q&A turn to the conversation history.
        
        Args:
            user_id: User identifier
            question: User's question
            answer: Bot's answer
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            logger.warning("Redis not available, cannot save conversation")
            return False
        
        try:
            key = self._get_key(user_id)
            
            # Create turn object
            turn = {
                'question': question,
                'answer': answer,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Get existing conversation
            conversation = self.get_conversation(user_id)
            
            # Add new turn
            conversation.append(turn)
            
            # Keep only last N turns (configurable)
            max_turns = self.config.max_conversation_turns
            if len(conversation) > max_turns:
                conversation = conversation[-max_turns:]
            
            # Save back to Redis with TTL
            self.redis_client.setex(
                name=key,
                time=self.config.conversation_ttl_seconds,
                value=json.dumps(conversation)
            )
            
            logger.debug(f"Saved conversation turn for user {user_id} (total: {len(conversation)} turns)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save conversation turn: {e}")
            return False
    
    def get_conversation(self, user_id: str) -> List[Dict]:
        """
        Get conversation history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of conversation turns (Q&A pairs)
        """
        if not self.redis_client:
            logger.warning("Redis not available, returning empty conversation")
            return []
        
        try:
            key = self._get_key(user_id)
            
            # Get conversation from Redis
            conversation_json = self.redis_client.get(key)
            
            if not conversation_json:
                logger.debug(f"No conversation history found for user {user_id}")
                return []
            
            # Parse JSON
            conversation = json.loads(conversation_json)
            logger.debug(f"Retrieved {len(conversation)} turns for user {user_id}")
            
            return conversation
            
        except Exception as e:
            logger.error(f"Failed to retrieve conversation: {e}")
            return []
    
    def get_context_string(self, user_id: str, max_turns: int = 5) -> str:
        """
        Get conversation history formatted as a context string for the LLM.
        
        Args:
            user_id: User identifier
            max_turns: Maximum number of recent turns to include (default: 5)
        """
        conversation = self.get_conversation(user_id)
        
        if not conversation:
            return ""
        
        # Only use last N turns
        recent_conversation = conversation[-max_turns:] if len(conversation) > max_turns else conversation
        
        # Build context string
        context_parts = ["Previous conversation:"]
        
        for turn in recent_conversation:  # ← ONLY RECENT TURNS!
            context_parts.append(f"User: {turn['question']}")
            context_parts.append(f"Assistant: {turn['answer']}")
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def clear_conversation(self, user_id: str) -> bool:
        """
        Clear conversation history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            logger.warning("Redis not available, cannot clear conversation")
            return False
        
        try:
            key = self._get_key(user_id)
            self.redis_client.delete(key)
            logger.info(f"Cleared conversation for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear conversation: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """
        Get statistics about stored conversations.
        
        Returns:
            Dictionary with stats
        """
        if not self.redis_client:
            return {'error': 'Redis not available'}
        
        try:
            # Count conversation keys
            pattern = "conversation:*"
            keys = self.redis_client.keys(pattern)
            
            stats = {
                'total_conversations': len(keys),
                'redis_connected': True,
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {'error': str(e)}
    
    def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.
        
        Returns:
            True if connected, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False


# ===== EXAMPLE USAGE =====
if __name__ == "__main__":
    """
    Test the conversation memory system.
    Run: python -m src.memory.conversation_memory
    """
    
    # Set up basic logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Create memory instance
    memory = ConversationMemory()
    
    # Test health check
    if not memory.health_check():
        print("❌ Redis is not connected. Check your configuration!")
        exit(1)
    
    print("✅ Redis connected!")
    
    # Simulate a conversation
    user_id = "test_user_123"
    
    print(f"\n--- Testing conversation memory for user: {user_id} ---")
    
    # Clear any existing conversation
    memory.clear_conversation(user_id)
    
    # Add some turns
    print("\n1. Adding first turn...")
    memory.add_turn(user_id, "Wie is Daoud?", "Daoud is verantwoordelijk voor management.")
    
    print("2. Adding second turn...")
    memory.add_turn(user_id, "Wat zijn zijn taken?", "Zijn taken zijn management ondersteuning.")
    
    print("3. Adding third turn...")
    memory.add_turn(user_id, "En Sarah?", "Sarah is verantwoordelijk voor training.")
    
    # Retrieve conversation
    print("\n--- Retrieving conversation history ---")
    conversation = memory.get_conversation(user_id)
    print(f"Found {len(conversation)} turns:")
    for i, turn in enumerate(conversation, 1):
        print(f"\nTurn {i}:")
        print(f"  Q: {turn['question']}")
        print(f"  A: {turn['answer']}")
    
    # Get formatted context
    print("\n--- Formatted context for LLM ---")
    context = memory.get_context_string(user_id)
    print(context)
    
    # Get stats
    print("\n--- Memory stats ---")
    stats = memory.get_stats()
    print(f"Total conversations stored: {stats.get('total_conversations', 0)}")
    
    # Clean up
    print("\n--- Cleaning up test data ---")
    memory.clear_conversation(user_id)
    print("✓ Test complete!")