"""
🎛️ YamieBot System Status - Control Panel

This script shows you the current state of your chatbot system:
- What PDFs are loaded
- How many vectors are in Pinecone
- Current configuration settings
- System health check

Run this BEFORE making any changes to understand your baseline.

Usage:
    python scripts/system_status.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_config
from pinecone import Pinecone
import os


def print_header(text):
    """Pretty print section headers"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def check_data_files():
    """Check what document files are in the data directory"""
    print_header("📁 DATA FILES")
    
    config = get_config()
    data_dir = Path(config.data_dir)
    
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return []
    
    # Get all supported document files (PDF, DOCX, etc.)
    all_files = []
    for ext in config.supported_extensions:
        all_files.extend(list(data_dir.glob(f"*{ext}")))
    
    if not all_files:
        print(f"⚠️  No document files found in {data_dir}")
        print(f"     Looking for: {', '.join(config.supported_extensions)}")
        return []
    
    print(f"\nFound {len(all_files)} document file(s):\n")
    
    total_size = 0
    for i, doc_file in enumerate(all_files, 1):
        size_kb = doc_file.stat().st_size / 1024
        total_size += size_kb
        print(f"  {i}. {doc_file.name}")
        print(f"     Size: {size_kb:.1f} KB")
        print(f"     Type: {doc_file.suffix.upper()}")
        print(f"     Path: {doc_file}")
        print()
    
    print(f"Total data size: {total_size:.1f} KB ({total_size/1024:.2f} MB)")
    
    return all_files


def check_pinecone_status():
    """Check Pinecone vector database status"""
    print_header("🗄️  PINECONE VECTOR DATABASE")
    
    try:
        config = get_config()
        pc = Pinecone(api_key=config.pinecone_api_key)
        
        # Check if index exists
        existing_indexes = pc.list_indexes().names()
        
        print(f"\nIndex name: {config.pinecone_index_name}")
        print(f"Namespace: {config.pinecone_namespace}")
        
        if config.pinecone_index_name not in existing_indexes:
            print(f"\n❌ Index '{config.pinecone_index_name}' does NOT exist!")
            print(f"   Available indexes: {existing_indexes if existing_indexes else 'None'}")
            print(f"\n   → You need to run ingestion first!")
            return None
        
        print(f"✅ Index exists")
        
        # Get index stats
        index = pc.Index(config.pinecone_index_name)
        stats = index.describe_index_stats()
        
        total_vectors = stats.get('total_vector_count', 0)
        namespace_stats = stats.get('namespaces', {})
        namespace_vectors = namespace_stats.get(config.pinecone_namespace, {}).get('vector_count', 0)
        
        print(f"\n📊 Statistics:")
        print(f"   Total vectors (all namespaces): {total_vectors}")
        print(f"   Vectors in '{config.pinecone_namespace}': {namespace_vectors}")
        print(f"   Dimension: {stats.get('dimension', 'unknown')}")
        
        if namespace_vectors == 0:
            print(f"\n⚠️  Warning: Namespace '{config.pinecone_namespace}' is empty!")
            print(f"   → Run ingestion to populate the index")
        
        # Check all namespaces
        if len(namespace_stats) > 1:
            print(f"\n   Other namespaces:")
            for ns, ns_stats in namespace_stats.items():
                if ns != config.pinecone_namespace:
                    print(f"     - {ns}: {ns_stats.get('vector_count', 0)} vectors")
        
        return stats
        
    except Exception as e:
        print(f"\n❌ Error connecting to Pinecone: {e}")
        return None


def check_configuration():
    """Display current configuration settings"""
    print_header("⚙️  CONFIGURATION")
    
    config = get_config()
    
    print("\n📄 Document Processing:")
    print(f"   Data directory: {config.data_dir}")
    print(f"   Supported extensions: {', '.join(config.supported_extensions)}")
    print(f"   Chunk size: {config.chunk_size} tokens")
    print(f"   Chunk overlap: {config.chunk_overlap} tokens")
    
    print("\n🤖 Embeddings:")
    print(f"   Model: {config.embedding_model}")
    print(f"   Dimensions: {config.embedding_dimensions}")
    print(f"   Batch size: {config.embedding_batch_size}")
    
    print("\n🔍 Retrieval:")
    print(f"   Top-K chunks: {config.query_top_k}")
    print(f"   Similarity threshold: {config.query_similarity_threshold}")
    
    print("\n💬 LLM (Answer Generation):")
    print(f"   Model: {config.llm_model}")
    print(f"   Temperature: {config.llm_temperature}")
    print(f"   Max tokens: {config.llm_max_tokens}")
    
    print("\n🔐 API Keys:")
    print(f"   OpenAI API Key: {'✅ Set' if config.openai_api_key else '❌ Missing'}")
    print(f"   Pinecone API Key: {'✅ Set' if config.pinecone_api_key else '❌ Missing'}")


def check_environment():
    """Check environment setup"""
    print_header("🌍 ENVIRONMENT")
    
    print("\n📦 Python Environment:")
    print(f"   Python version: {sys.version.split()[0]}")
    
    # Check if .env exists
    env_file = project_root / ".env"
    print(f"   .env file: {'✅ Found' if env_file.exists() else '❌ Not found'}")
    
    # Check required packages
    print("\n📚 Required Packages:")
    required = [
        "openai",
        "pinecone",
        "llama_index",
        "dotenv",
    ]
    
    for package in required:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (NOT INSTALLED)")


def health_check():
    """Overall system health check"""
    print_header("🏥 HEALTH CHECK")
    
    issues = []
    warnings = []
    
    # Check 1: Data files
    config = get_config()
    data_dir = Path(config.data_dir)
    
    if not data_dir.exists():
        issues.append("Data directory does not exist")
    else:
        # Check for any supported document files
        all_files = []
        for ext in config.supported_extensions:
            all_files.extend(list(data_dir.glob(f"*{ext}")))
        
        if not all_files:
            warnings.append(f"No document files ({', '.join(config.supported_extensions)}) in data directory")
    
    # Check 2: API keys
    if not config.openai_api_key:
        issues.append("OpenAI API key not set")
    if not config.pinecone_api_key:
        issues.append("Pinecone API key not set")
    
    # Check 3: Pinecone index
    try:
        pc = Pinecone(api_key=config.pinecone_api_key)
        if config.pinecone_index_name not in pc.list_indexes().names():
            warnings.append("Pinecone index does not exist (need to run ingestion)")
        else:
            index = pc.Index(config.pinecone_index_name)
            stats = index.describe_index_stats()
            namespace_vectors = stats.get('namespaces', {}).get(config.pinecone_namespace, {}).get('vector_count', 0)
            if namespace_vectors == 0:
                warnings.append("Pinecone namespace is empty (need to run ingestion)")
    except Exception as e:
        issues.append(f"Cannot connect to Pinecone: {e}")
    
    # Display results
    if not issues and not warnings:
        print("\n✅ System is healthy and ready to use!")
    else:
        if issues:
            print("\n❌ CRITICAL ISSUES:")
            for issue in issues:
                print(f"   • {issue}")
        
        if warnings:
            print("\n⚠️  WARNINGS:")
            for warning in warnings:
                print(f"   • {warning}")
    
    return len(issues) == 0


def main():
    print("\n" + "=" * 80)
    print("  🎛️  YAMIEBOT SYSTEM STATUS")
    print("=" * 80)
    print("\nThis script shows the current state of your chatbot system.")
    print("Run this before making changes to understand your baseline.\n")
    
    try:
        # Run all checks
        check_environment()
        check_configuration()
        check_data_files()
        check_pinecone_status()
        is_healthy = health_check()
        
        # Summary
        print_header("📝 SUMMARY")
        if is_healthy:
            print("\n✅ Your system is ready to use!")
            print("\n   Next steps:")
            print("   1. Run 'python scripts/test_query.py' to test queries")
            print("   2. Or run 'python scripts/test_suite.py' for comprehensive testing")
        else:
            print("\n⚠️  Your system has issues that need to be fixed.")
            print("\n   Next steps:")
            print("   1. Fix the issues listed above")
            print("   2. If Pinecone is empty, run 'python scripts/run_ingestion.py'")
            print("   3. Then run this script again to verify")
        
        print("\n" + "=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error during system check: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()