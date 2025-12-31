"""
Quick test script to verify Redis connection and conversation memory.

Usage:
    python scripts/test_redis.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.memory.conversation_memory import ConversationMemory

def main():
    print("=" * 80)
    print("  REDIS CONNECTION TEST")
    print("=" * 80)
    
    # Create memory instance
    print("\n1. Creating ConversationMemory instance...")
    memory = ConversationMemory()
    
    # Health check
    print("\n2. Testing Redis connection...")
    if memory.health_check():
        print("   ✅ Redis is connected and working!")
    else:
        print("   ❌ Redis connection failed!")
        print("\n   Troubleshooting:")
        print("   - Check your .env file has REDIS_HOST, REDIS_PORT, REDIS_PASSWORD")
        print("   - Verify your Redis Cloud database is active")
        print("   - Test connection in Redis Cloud dashboard")
        return
    
    # Test conversation storage
    print("\n3. Testing conversation storage...")
    test_user = "test_user_123"
    
    # Clear any existing data
    memory.clear_conversation(test_user)
    
    # Add a turn
    memory.add_turn(test_user, "Hoe heet jij?", "Ik ben YamieBot!")
    
    # Retrieve it
    conversation = memory.get_conversation(test_user)
    
    if conversation and len(conversation) == 1:
        print("   ✅ Successfully saved and retrieved conversation!")
        print(f"   Q: {conversation[0]['question']}")
        print(f"   A: {conversation[0]['answer']}")
    else:
        print("   ❌ Failed to save/retrieve conversation")
        return
    
    # Test context string
    print("\n4. Testing context formatting...")
    memory.add_turn(test_user, "Wat kun je doen?", "Ik kan vragen beantwoorden over Smokey Joe's!")
    context = memory.get_context_string(test_user)
    
    if context:
        print("   ✅ Context string generated:")
        print("   " + "\n   ".join(context.split("\n")[:6]))  # Show first 6 lines
    else:
        print("   ❌ Failed to generate context")
    
    # Get stats
    print("\n5. Memory statistics...")
    stats = memory.get_stats()
    print(f"   Total conversations: {stats.get('total_conversations', 0)}")
    
    # Cleanup
    print("\n6. Cleaning up test data...")
    memory.clear_conversation(test_user)
    print("   ✅ Test data cleared")
    
    print("\n" + "=" * 80)
    print("  ✅ ALL TESTS PASSED! Redis is ready to use!")
    print("=" * 80)

if __name__ == "__main__":
    main()