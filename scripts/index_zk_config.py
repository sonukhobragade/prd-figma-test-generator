#!/usr/bin/env python3
"""
Index ZK Configuration Documentation into RAG

This script indexes the ZK_CONFIG_BEHAVIOR_GUIDE.md file into:
1. zk_config_docs collection - Dedicated config documentation (per-section)
2. prd_documents_v1 collection - General PRD retrieval (chunked)

Usage:
    # Ensure Qdrant is running
    docker-compose up -d

    # Run the indexing script
    python scripts/index_zk_config.py

    # Verify indexing
    curl http://localhost:6333/collections/zk_config_docs
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv  # noqa: E402  (needs the path/env setup above)

# Load environment variables
load_dotenv(project_root / ".env")


async def main():
    """Main entry point for ZK Config indexing."""

    print("=" * 60)
    print("ZK Configuration Documentation Indexer")
    print("=" * 60)

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[ERROR] OPENAI_API_KEY not found in environment")
        print("Please set it in your .env file or environment variables")
        return 1

    # Import RAG integration
    try:
        from framework.rag_integration import TestCaseRAG
    except ImportError as e:
        print(f"\n[ERROR] Failed to import TestCaseRAG: {e}")
        print("Make sure you're running from the project root directory")
        return 1

    # Initialize RAG
    print("\n[1/4] Initializing RAG system...")
    rag = TestCaseRAG(
        qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
        qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),  # matches docker-compose.yml
    )

    if not rag.enabled:
        print("\n[ERROR] RAG system not available")
        print("Please ensure Qdrant is running:")
        print("  docker-compose up -d")
        return 1

    print("  RAG system initialized successfully")

    # Read the ZK Config markdown file
    print("\n[2/4] Reading ZK Config documentation...")

    # No config guide ships with this repo; supply your own. The API also
    # accepts one by upload, see routes/zk.py.
    config_paths = [
        Path(os.getenv("ZK_CONFIG_GUIDE", "")) if os.getenv("ZK_CONFIG_GUIDE") else None,
        project_root / "docs" / "zookeeper" / "config_guide.md",
    ]
    config_paths = [p for p in config_paths if p is not None]

    config_content = None
    config_path = None

    for path in config_paths:
        if path.exists():
            config_path = path
            config_content = path.read_text(encoding="utf-8")
            break

    if not config_content:
        print("\n[ERROR] ZK Config documentation not found")
        print("Expected locations:")
        for path in config_paths:
            print(f"  - {path}")
        return 1

    print(f"  Found: {config_path}")
    print(f"  Size: {len(config_content):,} characters")

    # Index the configuration
    print("\n[3/4] Indexing ZK Config documentation...")
    print("  - Indexing into zk_config_docs (per-section)")
    print("  - Indexing into prd_documents_v1 (chunked)")

    stats = await rag.index_zk_config(
        config_content=config_content,
        doc_name="ZK_CONFIG_BEHAVIOR_GUIDE",
        also_index_as_prd=True,
        chunk_size=1500,
        chunk_overlap=300,
    )

    if stats["status"] == "success":
        print("\n  Indexing complete!")
        print(f"  - ZK Config sections indexed: {stats['zk_config_chunks']}")
        print(f"  - PRD chunks indexed: {stats['prd_chunks']}")
    else:
        print(f"\n  [ERROR] Indexing failed: {stats.get('error_message', 'Unknown error')}")
        return 1

    # Verify indexing
    print("\n[4/4] Verifying indexing...")

    rag_stats = rag.get_rag_stats()

    print("\n  RAG Collections Status:")
    print(f"  - test_cases_v1:      {rag_stats.get('test_cases', {}).get('count', 0):,} documents")
    print(f"  - prd_documents_v1:   {rag_stats.get('prd_documents', {}).get('count', 0):,} documents")
    print(f"  - coverage_insights:  {rag_stats.get('coverage_insights', {}).get('count', 0):,} documents")
    print(f"  - zk_config_docs:     {rag_stats.get('zk_config_docs', {}).get('count', 0):,} documents")
    print(f"  - Total:              {rag_stats.get('total_documents', 0):,} documents")

    # Test retrieval
    print("\n  Testing retrieval...")

    test_queries = [
        "payment configuration minimum deposit",
        "chat streaming typing speed",
        "force update version",
    ]

    for query in test_queries:
        results = rag.get_config_context(query, top_k=2)
        if results:
            print(f"\n  Query: '{query}'")
            for r in results:
                meta = r.get("metadata", {})
                print(f"    - {meta.get('config_key', 'N/A')} ({meta.get('category', 'N/A')}) - {r.get('score', 0)*100:.0f}% match")
        else:
            print(f"\n  Query: '{query}' - No results")

    print("\n" + "=" * 60)
    print("ZK Config indexing complete!")
    print("=" * 60)
    print("\nYou can now generate test cases with ZK Config context.")
    print("The RAG system will automatically retrieve relevant config settings")
    print("when analyzing features like payment, chat, navigation, etc.")


if __name__ == "__main__":
    # Failure paths return 1. Without propagating it, asyncio.run() discards
    # the value and the process exits 0, so a failed index looked successful
    # to any automation that checked the exit status.
    raise SystemExit(asyncio.run(main()) or 0)
