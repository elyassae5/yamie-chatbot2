"""
Inspect Redis database to see what conversations are stored.

This will show you EXACTLY what's in Redis that might be causing issues.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.memory.conversation_memory import ConversationMemory
import json

def main():
    print("=" * 80)
    print("REDIS DATABASE INSPECTOR")
    print("=" * 80)
    
    # Connect to Redis
    memory = ConversationMemory()
    
    # Check connection
    if not memory.health_check():
        print("\n❌ Redis is not connected!")
        return
    
    print("\n✅ Connected to Redis!")
    
    # Get all conversation keys
    try:
        all_keys = memory.redis_client.keys("conversation:*")
        
        if not all_keys:
            print("\n📭 No conversations stored in Redis")
            return
        
        print(f"\n📊 Found {len(all_keys)} conversation(s) in Redis:\n")
        
        for key in all_keys:
            print("=" * 80)
            print(f"KEY: {key}")
            print("=" * 80)
            
            # Get the conversation
            conversation_json = memory.redis_client.get(key)
            
            if conversation_json:
                conversation = json.loads(conversation_json)
                
                print(f"Number of turns: {len(conversation)}")
                print(f"\nConversation history:")
                print("-" * 80)
                
                for i, turn in enumerate(conversation, 1):
                    print(f"\nTurn {i}:")
                    print(f"  Time: {turn.get('timestamp', 'N/A')}")
                    print(f"  Q: {turn.get('question', 'N/A')[:100]}...")
                    print(f"  A: {turn.get('answer', 'N/A')[:200]}...")
                
                # Check TTL
                ttl = memory.redis_client.ttl(key)
                if ttl > 0:
                    minutes = ttl // 60
                    print(f"\n⏰ TTL: {ttl} seconds ({minutes} minutes remaining)")
                else:
                    print(f"\n⏰ TTL: Expired or no TTL set")
            
            print("\n")
        
        # Ask if user wants to clear
        print("=" * 80)
        choice = input("\nDo you want to CLEAR all conversations? (yes/no): ").strip().lower()
        
        if choice in ['yes', 'y']:
            for key in all_keys:
                memory.redis_client.delete(key)
            print("\n✅ All conversations cleared!")
        else:
            print("\n📝 Conversations kept as-is")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()