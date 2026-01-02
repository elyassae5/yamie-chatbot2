"""
Run YamieBot Backend Server

Simple script to start the FastAPI backend.

Usage:
    python run_backend.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn
from backend.config import get_backend_config

if __name__ == "__main__":
    config = get_backend_config()
    
    print("\n" + "="*80)
    print("🚀 STARTING YAMIEBOT BACKEND")
    print("="*80)
    print(f"  Host: {config.host}")
    print(f"  Port: {config.port}")
    print(f"  Docs: http://localhost:{config.port}/docs")
    print(f"  Health: http://localhost:{config.port}/api/health")
    print(f"  Query: http://localhost:{config.port}/api/query")
    print("="*80)
    print("\n⚠️  Press Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "backend.main:app",
        host=config.host,
        port=config.port,
        reload=False,  # Set to True for development auto-reload
        log_level="info"
    )