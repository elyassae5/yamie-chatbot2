"""
Backend Routes

Import all route modules here for easy inclusion in main.py
"""

from backend.routes import query, health, webhook

__all__ = ["query", "health", "webhook"]