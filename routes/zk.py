"""ZooKeeper Config Sync routes."""

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from routes.dependencies import OUTPUT_DIR, get_rag

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["ZooKeeper Config"])


@router.get("/zk/status")
async def get_zk_status():
    """Get ZooKeeper config sync status.

    Returns:
        JSON with ZK connection status and indexed config count.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "enabled": False,
            "message": "RAG system not available",
            "zk_live_config_count": 0,
        })

    try:
        stats = rag.get_rag_stats()
        zk_count = stats.get("zk_live_config", {}).get("count", 0)

        return JSONResponse(content={
            "success": True,
            "enabled": True,
            "zk_live_config_count": zk_count,
            "zk_config_docs_count": stats.get("zk_config_docs", {}).get("count", 0),
            "last_sync": None,
        })
    except Exception as e:
        logger.error(f"Error getting ZK status: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e),
        })


@router.post("/zk/sync")
async def sync_zk_configs():
    """Sync ZooKeeper configs from ZK-Web to RAG.

    Fetches all configs from ZK-Web and indexes them into zk_live_config collection.
    Tracks added, removed, and modified configs for changelog.

    Returns:
        JSON with sync results including detailed diff of changes.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        raise HTTPException(status_code=503, detail="RAG system not available")

    # Check required environment variables
    required_vars = ["ZK_NAVIGATOR_URL", "ZK_NAVIGATOR_USER", "ZK_NAVIGATOR_PASS", "ZK_ADDRESS"]
    missing_vars = [v for v in required_vars if not os.getenv(v)]

    if missing_vars:
        raise HTTPException(
            status_code=400,
            detail=f"Missing ZK configuration: {missing_vars}. Set them in .env file."
        )

    try:
        from framework.zk_client import ZKWebClient, format_configs_for_indexing

        # Load previous config snapshot for diff comparison
        snapshot_path = OUTPUT_DIR / "zk_config_snapshot.json"
        previous_configs = {}
        if snapshot_path.exists():
            try:
                previous_configs = json.loads(snapshot_path.read_text())
            except Exception:
                previous_configs = {}

        # Initialize ZK client
        zk_client = ZKWebClient(
            base_url=os.getenv("ZK_NAVIGATOR_URL"),
            username=os.getenv("ZK_NAVIGATOR_USER"),
            password=os.getenv("ZK_NAVIGATOR_PASS"),
            zk_address=os.getenv("ZK_ADDRESS"),
        )

        # Get paths to index
        paths_to_index = os.getenv("ZK_INDEX_PATHS", "/myapp").split(",")
        paths_to_index = [p.strip() for p in paths_to_index if p.strip()]

        # Fetch all configs
        all_configs = await zk_client.get_all_configs(
            paths=paths_to_index,
            max_depth=10,
            filter_sensitive=True,
        )

        await zk_client.close()

        if not all_configs:
            return JSONResponse(content={
                "success": True,
                "message": "No configs found to sync",
                "configs_synced": 0,
                "added": [],
                "removed": [],
                "modified": [],
            })

        # Build current config snapshot with hashes for comparison
        current_configs = {}
        for path, node in all_configs.items():
            data_hash = hashlib.md5((node.data or "").encode()).hexdigest()
            current_configs[path] = {
                "hash": data_hash,
                "data_preview": node.data or "",  # Full data for proper diff computation
                "version": node.version,
            }

        # Calculate diff
        previous_paths = set(previous_configs.keys())
        current_paths = set(current_configs.keys())

        added_paths = current_paths - previous_paths
        removed_paths = previous_paths - current_paths
        common_paths = current_paths & previous_paths

        # Check for modifications in common paths
        modified_paths = []
        for path in common_paths:
            if current_configs[path]["hash"] != previous_configs.get(path, {}).get("hash"):
                modified_paths.append(path)

        # Format diff details
        added = [{"path": p, "preview": current_configs[p]["data_preview"]} for p in sorted(added_paths)]
        removed = [{"path": p, "preview": previous_configs.get(p, {}).get("data_preview", "")} for p in sorted(removed_paths)]
        modified = [
            {
                "path": p,
                "old_preview": previous_configs.get(p, {}).get("data_preview", ""),
                "new_preview": current_configs[p]["data_preview"],
            }
            for p in sorted(modified_paths)
        ]

        # Format for indexing
        documents = format_configs_for_indexing(all_configs)

        # Index configs
        await rag.index_zk_live_configs(documents)

        # Save current snapshot for next diff
        snapshot_path.write_text(json.dumps(current_configs, indent=2))

        # Save sync metadata
        sync_time = datetime.now().isoformat()

        # Save changelog entry with detailed diff
        changelog_path = OUTPUT_DIR / "zk_changelog.json"
        changelog = []
        if changelog_path.exists():
            try:
                changelog = json.loads(changelog_path.read_text())
            except Exception:
                changelog = []

        changelog.insert(0, {
            "sync_time": sync_time,
            "total_configs": len(current_configs),
            "previous_count": len(previous_configs),
            "summary": {
                "added": len(added),
                "removed": len(removed),
                "modified": len(modified),
                "unchanged": len(common_paths) - len(modified_paths),
            },
            "added": added[:20],
            "removed": removed[:20],
            "modified": modified[:20],
            "paths_synced": paths_to_index,
        })

        # Keep only last 50 changelog entries
        changelog = changelog[:50]
        changelog_path.write_text(json.dumps(changelog, indent=2))

        return JSONResponse(content={
            "success": True,
            "message": f"Synced {len(current_configs)} configs from ZooKeeper",
            "configs_synced": len(current_configs),
            "previous_count": len(previous_configs),
            "summary": {
                "added": len(added),
                "removed": len(removed),
                "modified": len(modified),
            },
            "added": added[:10],
            "removed": removed[:10],
            "modified": modified[:10],
            "sync_time": sync_time,
        })

    except Exception as e:
        logger.error(f"Error syncing ZK configs: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/zk/changelog")
async def get_zk_changelog(limit: int = 20):
    """Get ZooKeeper config sync changelog.

    Shows history of sync operations and config changes.

    Args:
        limit: Maximum number of changelog entries to return.

    Returns:
        JSON with changelog entries.
    """
    changelog_path = OUTPUT_DIR / "zk_changelog.json"

    if not changelog_path.exists():
        return JSONResponse(content={
            "success": True,
            "changelog": [],
            "message": "No sync history yet. Run a sync first.",
        })

    try:
        changelog = json.loads(changelog_path.read_text())
        return JSONResponse(content={
            "success": True,
            "changelog": changelog[:limit],
            "total_entries": len(changelog),
        })
    except Exception as e:
        logger.error(f"Error reading changelog: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e),
            "changelog": [],
        })


@router.get("/zk/configs")
async def list_zk_configs(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
):
    """List indexed ZK configs.

    Args:
        category: Filter by category (payments, chatBot, etc.)
        search: Search query for config content
        limit: Maximum number of configs to return

    Returns:
        JSON with list of indexed configs.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "configs": [],
            "message": "RAG system not available",
        })

    try:
        if search:
            # Search using RAG
            results = rag.get_live_config_context(
                query=search,
                category_filter=category,
                top_k=limit,
            )
            configs = [
                {
                    "path": r.get("metadata", {}).get("path"),
                    "config_name": r.get("metadata", {}).get("config_name"),
                    "category": r.get("metadata", {}).get("category"),
                    "score": r.get("score"),
                    "text": r.get("text", ""),
                }
                for r in results
            ]
        else:
            # List all (using a broad query)
            results = rag.get_live_config_context(
                query="configuration settings",
                category_filter=category,
                top_k=limit,
            )
            configs = [
                {
                    "path": r.get("metadata", {}).get("path"),
                    "config_name": r.get("metadata", {}).get("config_name"),
                    "category": r.get("metadata", {}).get("category"),
                    "text": r.get("text", ""),
                }
                for r in results
            ]

        return JSONResponse(content={
            "success": True,
            "configs": configs,
            "count": len(configs),
        })

    except Exception as e:
        logger.error(f"Error listing ZK configs: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e),
            "configs": [],
        })


# =============================================================================
# ZK Config Documentation Endpoints (NEW)
# =============================================================================

@router.get("/zk/docs/status")
async def get_zk_docs_status():
    """Get ZK config documentation status.

    Returns:
        JSON with doc count, last updated, and categories.
    """
    rag = get_rag()
    docs_meta_path = OUTPUT_DIR / "zk_docs_metadata.json"

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "enabled": False,
            "message": "RAG system not available",
            "docs_count": 0,
        })

    try:
        # Get doc count from RAG stats
        stats = rag.get_rag_stats()
        docs_count = stats.get("zk_config_docs", {}).get("count", 0)

        # Load metadata if exists
        metadata = {}
        if docs_meta_path.exists():
            try:
                metadata = json.loads(docs_meta_path.read_text())
            except Exception:
                metadata = {}

        return JSONResponse(content={
            "success": True,
            "enabled": True,
            "docs_count": docs_count,
            "last_updated": metadata.get("last_updated"),
            "source_file": metadata.get("source_file", "Not uploaded yet"),
            "categories": metadata.get("categories", {}),
            "parse_stats": metadata.get("parse_stats", {}),
        })
    except Exception as e:
        logger.error(f"Error getting ZK docs status: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e),
        })


@router.post("/zk/docs/upload")
async def upload_zk_docs(file: UploadFile = File(...)):
    """Upload ZK_CONFIG_BEHAVIOR_GUIDE.md for indexing.

    Parses the markdown file and indexes each config's documentation
    into the zk_config_docs collection for RAG search.

    Args:
        file: Markdown file to upload

    Returns:
        JSON with upload results and parsed config count.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        raise HTTPException(status_code=503, detail="RAG system not available")

    # Validate file type
    if not file.filename.endswith('.md'):
        raise HTTPException(status_code=400, detail="Only .md files are supported")

    try:
        from framework.zk_config_parser import ZKConfigBehaviorParser

        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')

        # Parse the markdown
        parser = ZKConfigBehaviorParser()
        docs = parser.parse_markdown(content_str)

        if not docs:
            return JSONResponse(content={
                "success": False,
                "message": "No config documentation found in the file",
                "docs_count": 0,
            })

        # Prepare documents for indexing
        index_docs = []
        for doc in docs:
            index_docs.append({
                "config_name": doc.config_name,
                "category": doc.category,
                "config_type": doc.config_type,
                "description": doc.description,
                "behavioral_impact": doc.behavioral_impact,
                "examples": doc.examples,
                "implementation_ref": doc.implementation_ref,
                "default_value": doc.default_value,
                "related_configs": doc.related_configs,
                "embedding_text": doc.to_embedding_text(),
            })

        # Index to RAG
        indexed_count = await rag.index_zk_config_docs(index_docs)

        # Save metadata
        docs_meta_path = OUTPUT_DIR / "zk_docs_metadata.json"
        metadata = {
            "last_updated": datetime.now().isoformat(),
            "source_file": file.filename,
            "docs_count": len(docs),
            "categories": parser.categories,
            "parse_stats": parser.get_stats(),
        }
        docs_meta_path.write_text(json.dumps(metadata, indent=2))

        # Also save the full parsed docs for quick access
        docs_data_path = OUTPUT_DIR / "zk_docs_parsed.json"
        docs_data_path.write_text(json.dumps([d.to_dict() for d in docs], indent=2))

        return JSONResponse(content={
            "success": True,
            "message": f"Successfully indexed {len(docs)} config documentations",
            "docs_count": len(docs),
            "indexed_count": indexed_count,
            "categories": parser.categories,
            "stats": parser.get_stats(),
        })

    except Exception as e:
        logger.error(f"Error uploading ZK docs: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/zk/docs/search")
async def search_zk_docs(
    q: str,
    category: Optional[str] = None,
    limit: int = 10,
):
    """Search ZK config documentation.

    Args:
        q: Search query (config name or behavior description)
        category: Filter by category
        limit: Maximum results

    Returns:
        JSON with matching config documentations.
    """
    rag = get_rag()

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "configs": [],
            "message": "RAG system not available",
        })

    try:
        # Search using RAG
        results = rag.get_config_behavior_context(
            query=q,
            category_filter=category,
            top_k=limit,
        )

        return JSONResponse(content={
            "success": True,
            "configs": results,
            "count": len(results),
            "query": q,
        })

    except Exception as e:
        logger.error(f"Error searching ZK docs: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e),
            "configs": [],
        })


@router.get("/zk/docs/config/{config_name}")
async def get_zk_doc_by_name(config_name: str):
    """Get documentation for a specific config by name.

    Args:
        config_name: The config name (e.g., streamingEnabled)

    Returns:
        JSON with the full config documentation.
    """
    docs_data_path = OUTPUT_DIR / "zk_docs_parsed.json"

    if not docs_data_path.exists():
        return JSONResponse(content={
            "success": False,
            "message": "Config documentation not uploaded yet",
            "config": None,
        })

    try:
        docs = json.loads(docs_data_path.read_text())

        # Find the config (case-insensitive)
        config_lower = config_name.lower()
        found = None
        for doc in docs:
            if doc.get("config_name", "").lower() == config_lower:
                found = doc
                break

        if not found:
            return JSONResponse(content={
                "success": False,
                "message": f"Config '{config_name}' not found in documentation",
                "config": None,
            })

        return JSONResponse(content={
            "success": True,
            "config": found,
        })

    except Exception as e:
        logger.error(f"Error getting config doc: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e),
            "config": None,
        })


@router.get("/zk/docs/categories")
async def get_zk_doc_categories():
    """Get all config categories with their configs.

    Returns:
        JSON with categories and config names.
    """
    docs_meta_path = OUTPUT_DIR / "zk_docs_metadata.json"

    if not docs_meta_path.exists():
        return JSONResponse(content={
            "success": False,
            "message": "Config documentation not uploaded yet",
            "categories": {},
        })

    try:
        metadata = json.loads(docs_meta_path.read_text())
        return JSONResponse(content={
            "success": True,
            "categories": metadata.get("categories", {}),
            "total_configs": metadata.get("docs_count", 0),
        })

    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e),
            "categories": {},
        })


@router.get("/zk/docs/all")
async def get_all_zk_docs():
    """Get all parsed config documentations.

    Returns:
        JSON with all config docs grouped by category.
    """
    docs_data_path = OUTPUT_DIR / "zk_docs_parsed.json"

    if not docs_data_path.exists():
        return JSONResponse(content={
            "success": False,
            "message": "Config documentation not uploaded yet",
            "docs": [],
        })

    try:
        docs = json.loads(docs_data_path.read_text())

        # Group by category
        by_category = {}
        for doc in docs:
            category = doc.get("category", "Uncategorized")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(doc)

        return JSONResponse(content={
            "success": True,
            "docs": docs,
            "by_category": by_category,
            "total_count": len(docs),
        })

    except Exception as e:
        logger.error(f"Error getting all docs: {e}")
        return JSONResponse(content={
            "success": False,
            "error": str(e),
            "docs": [],
        })


@router.get("/zk/combined")
async def get_combined_config_view(
    search: Optional[str] = None,
    limit: int = 50,
):
    """Get combined view of live ZK values with their documentation.

    This endpoint merges:
    1. Live config values from zk_live_config collection
    2. Config documentation from zk_config_docs collection

    Returns:
        JSON with configs showing both live values and documentation.
    """
    rag = get_rag()
    docs_data_path = OUTPUT_DIR / "zk_docs_parsed.json"

    if not rag or not rag.enabled:
        return JSONResponse(content={
            "success": False,
            "configs": [],
            "message": "RAG system not available",
        })

    try:
        # Load parsed docs if available
        docs_by_name = {}
        if docs_data_path.exists():
            try:
                docs = json.loads(docs_data_path.read_text())
                for doc in docs:
                    config_name = doc.get("config_name", "").lower()
                    if config_name:
                        docs_by_name[config_name] = doc
            except Exception:
                pass

        # Get live configs
        live_results = rag.get_live_config_context(
            query=search or "configuration",
            top_k=limit,
        )

        # Build combined view
        combined = []
        seen_configs = set()

        for result in live_results:
            metadata = result.get("metadata", {})
            config_name = metadata.get("config_name", "")
            config_name_lower = config_name.lower()

            # Get documentation if available
            doc_info = docs_by_name.get(config_name_lower, {})

            combined.append({
                "config_name": config_name,
                "path": metadata.get("path", ""),
                "category": metadata.get("category", doc_info.get("category", "Unknown")),
                "live_value": result.get("text", ""),
                "last_synced": metadata.get("synced_at"),
                # Documentation fields
                "has_documentation": bool(doc_info),
                "config_type": doc_info.get("config_type", "unknown"),
                "description": doc_info.get("description", ""),
                "behavioral_impact": doc_info.get("behavioral_impact", ""),
                "examples": doc_info.get("examples", [])[:5],
                "implementation_ref": doc_info.get("implementation_ref", ""),
                "default_value": doc_info.get("default_value", ""),
            })
            seen_configs.add(config_name_lower)

        # Add documented configs that aren't in live (documentation-only)
        for config_name_lower, doc in docs_by_name.items():
            if config_name_lower not in seen_configs:
                combined.append({
                    "config_name": doc.get("config_name", ""),
                    "path": "",
                    "category": doc.get("category", "Unknown"),
                    "live_value": None,  # Not in live config
                    "last_synced": None,
                    "has_documentation": True,
                    "config_type": doc.get("config_type", "unknown"),
                    "description": doc.get("description", ""),
                    "behavioral_impact": doc.get("behavioral_impact", ""),
                    "examples": doc.get("examples", [])[:5],
                    "implementation_ref": doc.get("implementation_ref", ""),
                    "default_value": doc.get("default_value", ""),
                    "documentation_only": True,
                })

        # Sort by category then name
        combined.sort(key=lambda x: (x.get("category", ""), x.get("config_name", "")))

        # Calculate status counts
        live_and_documented = sum(1 for c in combined if c.get("live_value") and c.get("has_documentation"))
        live_only = sum(1 for c in combined if c.get("live_value") and not c.get("has_documentation"))
        doc_only = sum(1 for c in combined if c.get("documentation_only"))

        return JSONResponse(content={
            "success": True,
            "configs": combined[:limit],
            "total_count": len(combined),
            "status_counts": {
                "live_and_documented": live_and_documented,
                "live_only": live_only,
                "documentation_only": doc_only,
            },
        })

    except Exception as e:
        logger.error(f"Error getting combined view: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content={
            "success": False,
            "error": str(e),
            "configs": [],
        })
