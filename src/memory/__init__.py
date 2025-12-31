"""
Memory module for conversation history management.
Uses Redis for fast, persistent, multi-user conversation storage.
"""

from src.memory.conversation_memory import ConversationMemory

__all__ = ['ConversationMemory']
