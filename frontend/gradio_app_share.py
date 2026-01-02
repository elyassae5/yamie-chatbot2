"""
🍝 YamieBot - Gradio Frontend (PUBLIC SHARE MODE - Connected to FastAPI Backend)

This version:
1. Connects to FastAPI backend via HTTP
2. Creates a PUBLIC link for remote access
3. Perfect for demoing to your uncle!

Run:
1. Start backend: python run_backend.py
2. Start Gradio: python frontend/gradio_app_share.py (or use run_frontend.py)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent  # Go up TWO levels
sys.path.insert(0, str(project_root))

import gradio as gr
import requests
import hashlib
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend configuration
BACKEND_URL = "http://localhost:8000"
QUERY_ENDPOINT = f"{BACKEND_URL}/api/query"
HEALTH_ENDPOINT = f"{BACKEND_URL}/api/health"


def check_backend_health():
    """Check if backend is running and healthy."""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✓ Backend is {data['status']}")
            return True
        else:
            logger.error(f"Backend returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("❌ Cannot connect to backend. Is it running?")
        logger.error(f"   Make sure to run: python run_backend.py")
        return False
    except Exception as e:
        logger.error(f"Backend health check failed: {e}")
        return False


def respond(message, history, request: gr.Request):
    """
    Process user message by calling the FastAPI backend.
    
    Args:
        message: User's current message
        history: List of previous messages in the conversation
        request: Gradio request object (contains session info)
        
    Returns:
        Bot's response string
    """
    try:
        # Use Gradio's session hash as user ID
        # This is unique per browser session (tab/window)
        # Different from history-based hash - persists across "clear" clicks
        user_id = f"gradio_{request.session_hash[:8]}"
        
        logger.info(f"Sending query to backend (session: {user_id}): {message[:50]}...")
        
        # Call backend API with debug enabled
        response = requests.post(
            QUERY_ENDPOINT,
            json={
                "question": message,
                "user_id": user_id,
                "debug": True  # Enable debug mode
            },
            timeout=30
        )
        
        # Check if request was successful
        if response.status_code == 200:
            data = response.json()
            
            # Extract answer
            answer = data.get("answer", "No answer received")
            
            # Add source citations if available
            sources = data.get("sources", [])
            if sources and data.get("has_answer", False):
                unique_sources = list(set([s["source"] for s in sources]))
                answer += f"\n\n📄 **Sources:** {', '.join(unique_sources)}"
            
            # Add debug info if available
            debug_info = data.get("debug_info")
            if debug_info:
                answer += "\n\n" + "="*50
                answer += "\n🔍 **DEBUG INFO:**\n"
                
                # Show transformed question
                if debug_info.get("transformed_question"):
                    answer += f"\n**Original:** {debug_info['original_question']}"
                    answer += f"\n**Transformed:** {debug_info['transformed_question']}"
                
                # Show chunk stats
                answer += f"\n**Chunks Retrieved:** {debug_info['chunks_retrieved']}"
                
                # Show top chunks
                top_chunks = debug_info.get("top_chunks", [])
                if top_chunks:
                    answer += "\n\n**Top Chunks:**"
                    for i, chunk in enumerate(top_chunks, 1):
                        answer += f"\n  {i}. **{chunk['source']}** (score: {chunk['score']})"
                        answer += f"\n     Category: {chunk['category']}"
                        answer += f"\n     Preview: {chunk['text_preview'][:100]}..."
                
                answer += "\n" + "="*50
            
            # Add response time
            response_time = data.get("response_time_seconds", 0)
            answer += f"\n\n⚡ _{response_time:.2f}s_"
            
            logger.info(f"✓ Response received ({response_time:.2f}s)")
            return answer
            
        elif response.status_code == 400:
            error_data = response.json()
            logger.warning(f"Validation error: {error_data}")
            return f"❌ Invalid question: {error_data.get('detail', 'Please try again')}"
            
        elif response.status_code == 500:
            error_data = response.json()
            logger.error(f"Backend error: {error_data}")
            return f"❌ Server error: {error_data.get('detail', 'Please try again later')}"
            
        else:
            logger.error(f"Unexpected status code: {response.status_code}")
            return f"❌ Unexpected error (status {response.status_code}). Please try again."
        
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        return "⏱️ Request timed out. The query is taking too long. Please try a simpler question."
        
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to backend")
        return "❌ Cannot connect to backend. Please make sure the backend is running:\n\n`python run_backend.py`"
        
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        return f"❌ An error occurred: {str(e)}"


# Check backend on startup
print("\n" + "="*80)
print("🚀 STARTING GRADIO FRONTEND (PUBLIC SHARE MODE)")
print("="*80)
print(f"Backend URL: {BACKEND_URL}")
print("Checking backend health...")

if check_backend_health():
    print("✓ Backend is healthy and ready!")
else:
    print("⚠️  WARNING: Backend is not responding!")
    print("   Please start the backend first:")
    print("   → python run_backend.py")
    print("\n   Gradio will still start, but queries will fail.")

print("="*80 + "\n")


# Create the Gradio interface
demo = gr.ChatInterface(
    respond,
    title="🍝 YamieBot - Internal Assistant",
    description="""
    **Welcome to YamieBot!** 🎉
    
    I'm your AI assistant for Yamie PastaBar. Ask me anything about:
    - 📋 Company policies and procedures
    - 👥 Employee information and contacts
    - 🕐 Schedules and operations
    - 📖 Training materials
    - 🔧 Equipment and troubleshooting
    
    **Available in Dutch and English!** 🇳🇱 🇬🇧
    """,
    examples=[
        "Wie is Daoud en wat doet hij?",
        "What are the sick leave policies?",
        "Vertel me over de openingstijden",
        "How do I contact HR?",
        "Wat zijn de belangrijkste taken van een manager?",
        "Tell me about employee benefits",
    ],
)


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚀 LAUNCHING GRADIO - PUBLIC SHARE MODE")
    print("="*80)
    print("\n🌐 IMPORTANT: This will create a PUBLIC link!")
    print("   Anyone with the link can access the chatbot for 72 hours.")
    print("   Perfect for sharing with your uncle to test remotely!")
    print("\n📝 Instructions:")
    print("  1. Wait for the public link to be generated...")
    print("  2. Copy the 'https://xxxxx.gradio.live' link")
    print("  3. Share that link with your uncle via WhatsApp/Email")
    print("  4. He can test it from his phone or computer!")
    print("\n⚠️  Note:")
    print("  - The link expires after 72 hours")
    print("  - You need to keep this script running")
    print("  - Backend must also be running (python run_backend.py)")
    print("  - Press Ctrl+C to stop the server")
    print("\n💡 Architecture:")
    print("  Uncle's Phone → Public Link → Gradio (your PC) → FastAPI Backend → QueryEngine")
    print("\n" + "="*80 + "\n")
    
    # Launch with PUBLIC sharing
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,              # 🌐 CREATE PUBLIC LINK!
        show_error=True,
        quiet=False,
    )