"""
Run YamieBot Frontend (Gradio)

Simple script to start the Gradio interface.
Connects to the FastAPI backend.

Usage:
    python run_frontend.py              # Local only
    python run_frontend.py --share      # Public link (for remote demos)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import argparse


def main():
    """Run the Gradio frontend."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run YamieBot Gradio Frontend")
    parser.add_argument(
        '--share', 
        action='store_true', 
        help='Create a public share link (for remote access)'
    )
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🚀 STARTING YAMIEBOT FRONTEND")
    print("="*80)
    print("\n⚠️  IMPORTANT: Make sure backend is running first!")
    print("   → In another terminal: python run_backend.py")
    print("\n📝 Frontend Configuration:")
    
    if args.share:
        print("   Mode: PUBLIC SHARE (remote access enabled)")
        print("   A public link will be generated for 72 hours")
        print("="*80 + "\n")
        
        # Import and run share version
        from frontend.gradio_app_share import demo
        
    else:
        print("   Mode: LOCAL ONLY (localhost access)")
        print("   Access at: http://localhost:7860")
        print("\n💡 Tip: Use --share flag for public link")
        print("   → python run_frontend.py --share")
        print("="*80 + "\n")
        
        # Import and run local version
        from frontend.gradio_app import demo
    
    # Launch Gradio
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=args.share,
        show_error=True,
        quiet=False,
    )


if __name__ == "__main__":
    main()