#!/usr/bin/env python3
"""
RAG Setup & Index CLI

Simple command-line tool to:
1. Start Qdrant (if not running)
2. Index your codebase
3. Test retrieval

Usage:
    # Index your codebase
    python rag_index.py /path/to/your/project
    
    # Force reindex
    python rag_index.py /path/to/your/project --force
    
    # Test a query
    python rag_index.py --query "recharge payment flow"
    
    # Check stats
    python rag_index.py --stats
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from rag import SimpleRAG


def check_docker():
    """Check if Docker is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def check_qdrant():
    """Check if Qdrant is running."""
    try:
        import requests
        response = requests.get("http://localhost:6335/", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def start_qdrant():
    """Start Qdrant using docker-compose."""
    print("🐳 Starting Qdrant...")
    
    compose_file = Path(__file__).parent / "docker-compose.yml"
    
    if not compose_file.exists():
        print("❌ docker-compose.yml not found!")
        return False
    
    try:
        subprocess.run(
            ["docker-compose", "-f", str(compose_file), "up", "-d"],
            check=True
        )
        
        # Wait for Qdrant to be ready
        print("⏳ Waiting for Qdrant to start...")
        for _ in range(30):
            if check_qdrant():
                print("✅ Qdrant is running!")
                return True
            time.sleep(1)
        
        print("⚠️ Qdrant started but not responding yet. Try again in a few seconds.")
        return False
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Qdrant: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="RAG Setup & Index CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Index your codebase
    python rag_index.py /path/to/your/codebase
    
    # Force reindex everything
    python rag_index.py /path/to/project --force
    
    # Search for context
    python rag_index.py --query "subscription payment"
    
    # Check stats
    python rag_index.py --stats
        """
    )
    
    parser.add_argument(
        "project_path",
        nargs="?",
        help="Path to React Native project to index"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reindex (delete existing data)"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Test query to search"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show collection statistics"
    )
    parser.add_argument(
        "--start-qdrant",
        action="store_true",
        help="Start Qdrant if not running"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧠 RAG Setup & Index Tool")
    print("=" * 60)
    print()
    
    # Check Docker
    if not check_docker():
        print("❌ Docker is not running!")
        print("   Please start Docker Desktop and try again.")
        sys.exit(1)
    print("✅ Docker is running")
    
    # Check/Start Qdrant
    if not check_qdrant():
        print("⚠️ Qdrant is not running")
        
        if args.start_qdrant or input("Start Qdrant now? (y/n): ").lower() == 'y':
            if not start_qdrant():
                sys.exit(1)
        else:
            print("\n📋 To start Qdrant manually:")
            print("   cd /path/to/prd-figma-test-generator")
            print("   docker-compose up -d")
            sys.exit(1)
    else:
        print("✅ Qdrant is running")
    
    print()
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ OPENAI_API_KEY not set!")
        print("   Set it with: export OPENAI_API_KEY=sk-...")
        
        # Check .env file
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)
            if os.getenv("OPENAI_API_KEY"):
                print("✅ Loaded from .env file")
            else:
                sys.exit(1)
        else:
            sys.exit(1)
    
    print("✅ OpenAI API key configured")
    print()
    
    # Initialize RAG
    try:
        rag = SimpleRAG()
    except Exception as e:
        print(f"❌ Failed to initialize RAG: {e}")
        sys.exit(1)
    
    # Handle --stats
    if args.stats:
        stats = rag.get_stats()
        print("📊 Collection Statistics:")
        print(f"   Name: {stats['name']}")
        print(f"   Documents: {stats['points_count']}")
        print(f"   Status: {stats['status']}")
        return
    
    # Handle --query
    if args.query:
        print(f"🔍 Searching for: {args.query}")
        print("-" * 40)
        
        results = rag.search(args.query, top_k=5)
        
        if not results:
            print("No results found.")
        else:
            for i, result in enumerate(results, 1):
                print(f"\n[{i}] Score: {result['score']:.3f}")
                print(f"    File: {result['metadata'].get('file_path', 'Unknown')}")
                print(f"    Type: {result['metadata'].get('type', 'Unknown')}")
                if result['metadata'].get('component_name'):
                    print(f"    Component: {result['metadata']['component_name']}")
                print(f"    Preview: {result['text'][:200]}...")
        return
    
    # Handle indexing
    if args.project_path:
        project_path = os.path.expanduser(args.project_path)
        
        if not os.path.exists(project_path):
            print(f"❌ Path does not exist: {project_path}")
            sys.exit(1)
        
        print(f"📁 Project: {project_path}")
        print()
        
        # Index
        print("🔄 Indexing codebase... (this may take a few minutes)")
        print()
        
        try:
            stats = rag.index_codebase(project_path, force_reindex=args.force)
            
            print()
            print("=" * 60)
            print("✅ INDEXING COMPLETE!")
            print("=" * 60)
            print()
            print(f"   Status: {stats.get('status', 'unknown')}")
            print(f"   Files processed: {stats.get('files_processed', 0)}")
            print(f"   Chunks created: {stats.get('chunks_created', 0)}")
            print(f"   Screens found: {stats.get('screens_found', 0)}")
            print(f"   Components found: {stats.get('components_found', 0)}")
            print(f"   API calls found: {stats.get('api_calls_found', 0)}")
            print()
            
            if stats.get('status') == 'skipped':
                print("💡 Data already exists. Use --force to reindex.")
            
            print("🎉 Your codebase is now indexed and ready!")
            print()
            print("NEXT STEPS:")
            print("1. Test a search: python rag_index.py --query 'recharge payment'")
            print("2. Run test generator - it will use the RAG context automatically!")
            
        except Exception as e:
            print(f"❌ Indexing failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        # No arguments - show help
        print("No project path provided.")
        print()
        print("Quick start:")
        print("  python rag_index.py /path/to/your/react-native-project")
        print()
        print("For your project:")
        print("  python rag_index.py /path/to/your/codebase")
        print()
        print("Run with --help for more options.")


if __name__ == "__main__":
    main()
