#!/usr/bin/env python3
"""
Index Live ZooKeeper Configurations into RAG

This script connects to ZK-Web, fetches all configuration nodes,
and indexes them into the zk_live_config collection in Qdrant.

Usage:
    # Ensure Qdrant is running
    docker-compose up -d

    # Run the indexing script
    python scripts/index_zk_live.py

    # Verify indexing
    curl http://localhost:6335/collections/zk_live_config
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
    """Main entry point for live ZK config indexing."""

    print("=" * 60)
    print("Live ZooKeeper Configuration Indexer")
    print("=" * 60)

    # Check required environment variables
    required_vars = ["ZK_NAVIGATOR_URL", "ZK_NAVIGATOR_USER", "ZK_NAVIGATOR_PASS", "ZK_ADDRESS"]
    missing_vars = [v for v in required_vars if not os.getenv(v)]

    if missing_vars:
        print(f"\n[ERROR] Missing required environment variables: {missing_vars}")
        print("Please set them in your .env file:")
        print("  ZK_NAVIGATOR_URL=https://zkweb.example.com")
        print("  ZK_NAVIGATOR_USER=username")
        print("  ZK_NAVIGATOR_PASS=password")
        print("  ZK_ADDRESS=zk-host:2181")
        return

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[ERROR] OPENAI_API_KEY not found in environment")
        print("Please set it in your .env file")
        return

    # Import modules
    try:
        from framework.zk_client import ZKWebClient, format_configs_for_indexing
        from framework.rag_integration import TestCaseRAG
    except ImportError as e:
        print(f"\n[ERROR] Failed to import modules: {e}")
        print("Make sure you're running from the project root directory")
        return

    # Initialize ZK client
    print("\n[1/4] Connecting to ZK-Web...")

    zk_client = ZKWebClient(
        base_url=os.getenv("ZK_NAVIGATOR_URL"),
        username=os.getenv("ZK_NAVIGATOR_USER"),
        password=os.getenv("ZK_NAVIGATOR_PASS"),
        zk_address=os.getenv("ZK_ADDRESS"),
    )

    # Test connection
    test_node = await zk_client.get_node("/")
    if not test_node:
        print("\n[ERROR] Failed to connect to ZK-Web")
        print("Check your credentials and network connectivity")
        await zk_client.close()
        return

    print(f"  Connected! Root has {test_node.num_children} children")

    # Initialize RAG
    print("\n[2/4] Initializing RAG system...")

    rag = TestCaseRAG(
        qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
        qdrant_port=int(os.getenv("QDRANT_PORT", "6335")),
    )

    if not rag.enabled:
        print("\n[ERROR] RAG system not available")
        print("Please ensure Qdrant is running:")
        print("  docker-compose up -d")
        await zk_client.close()
        return

    print("  RAG system initialized successfully")

    # Get paths to index
    paths_to_index = os.getenv("ZK_INDEX_PATHS", "/myapp").split(",")
    paths_to_index = [p.strip() for p in paths_to_index if p.strip()]

    print(f"\n[3/4] Fetching configs from ZK paths: {paths_to_index}")

    # Fetch all configs
    all_configs = await zk_client.get_all_configs(
        paths=paths_to_index,
        max_depth=10,
        filter_sensitive=True,
    )

    if not all_configs:
        print("\n[WARNING] No configs found to index")
        await zk_client.close()
        return

    print(f"\n  Found {len(all_configs)} config nodes with data")

    # Show sample of what was found
    print("\n  Sample configs found:")
    for i, (path, node) in enumerate(list(all_configs.items())[:5]):
        data_preview = (node.data[:50] + "...") if node.data and len(node.data) > 50 else node.data
        print(f"    - {path}")
        print(f"      Data: {data_preview}")

    if len(all_configs) > 5:
        print(f"    ... and {len(all_configs) - 5} more")

    # Format for indexing
    print("\n[4/4] Indexing configs into RAG...")

    documents = format_configs_for_indexing(all_configs)

    stats = await rag.index_zk_live_configs(documents)

    if stats["status"] == "success":
        print("\n  Indexing complete!")
        print(f"  - Configs indexed: {stats['configs_indexed']}")
        print(f"  - Indexed at: {stats['indexed_at']}")
    else:
        print(f"\n  [ERROR] Indexing failed: {stats.get('error_message', 'Unknown error')}")
        await zk_client.close()
        return

    # Verify indexing
    print("\n  RAG Collections Status:")
    rag_stats = rag.get_rag_stats()
    print(f"  - zk_live_config:     {rag_stats.get('zk_live_config', {}).get('count', 0):,} documents")
    print(f"  - Total:              {rag_stats.get('total_documents', 0):,} documents")

    # Test retrieval
    print("\n  Testing retrieval...")

    test_queries = [
        "payment gateway configuration",
        "chat service config",
        "notification service",
    ]

    for query in test_queries:
        results = rag.get_live_config_context(query, top_k=2)
        if results:
            print(f"\n  Query: '{query}'")
            for r in results:
                meta = r.get("metadata", {})
                print(f"    - {meta.get('config_name', 'N/A')} ({meta.get('path', 'N/A')}) - {r.get('score', 0)*100:.0f}% match")
        else:
            print(f"\n  Query: '{query}' - No results")

    # Cleanup
    await zk_client.close()

    print("\n" + "=" * 60)
    print("Live ZK config indexing complete!")
    print("=" * 60)
    print("\nYou can now generate test cases with live ZK config context.")
    print("The RAG system will automatically retrieve relevant config values")
    print("when analyzing features like payment, chat, notification, etc.")


if __name__ == "__main__":
    asyncio.run(main())
