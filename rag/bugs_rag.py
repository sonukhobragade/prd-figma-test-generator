"""
Bugs RAG - Bug Knowledge Storage and Retrieval
===============================================

Stores bug documents in Qdrant for semantic search.
Used by test generation to learn from historical bugs.

Usage:
    bugs_rag = BugsRAG()

    # Store bugs from CSV
    bugs_rag.store_bugs(bug_documents)

    # Search for bugs related to a feature
    results = bugs_rag.search_bugs("subscription payment")

    # Get bugs for test generation context
    context = bugs_rag.get_bugs_context("subscription")
"""

import logging
from typing import Any, Dict, List, Optional

from .embeddings import EmbeddingProvider
from .qdrant_store import QdrantStore

# Import BugDocument from framework
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from framework.bugs_parser import BugDocument

logger = logging.getLogger(__name__)


class BugsRAG:
    """RAG system for bug knowledge."""

    COLLECTION_NAME = "bugs_knowledge"

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6335,
        embedding_provider: str = "local",
    ):
        """Initialize Bugs RAG.

        Args:
            qdrant_host: Qdrant host
            qdrant_port: Qdrant port
            embedding_provider: "openai" or "local"
        """
        # Initialize embedding provider
        self.embedder = EmbeddingProvider(provider=embedding_provider)

        # Initialize Qdrant store
        self.store = QdrantStore(
            collection_name=self.COLLECTION_NAME,
            host=qdrant_host,
            port=qdrant_port,
            dimension=self.embedder.dimension,
        )

        logger.info(f"BugsRAG initialized with collection: {self.COLLECTION_NAME}")

    def store_bugs(self, bugs: List[BugDocument]) -> Dict[str, Any]:
        """Store bug documents in Qdrant.

        Args:
            bugs: List of BugDocument objects

        Returns:
            Stats about the storage operation
        """
        if not bugs:
            return {"status": "empty", "stored": 0}

        # Convert bugs to text for embedding
        texts = [bug.to_rag_text() for bug in bugs]

        # Create metadata for each bug
        metadata = [bug.to_dict() for bug in bugs]

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(bugs)} bugs...")
        embeddings = self.embedder.embed(texts)

        # Store in Qdrant
        logger.info("Storing bugs in Qdrant...")
        ids = self.store.add_documents(texts, embeddings, metadata)

        stats = {
            "status": "success",
            "stored": len(bugs),
            "ids": ids,
        }

        logger.info(f"Stored {len(bugs)} bugs in collection {self.COLLECTION_NAME}")
        return stats

    def search_bugs(
        self,
        query: str,
        top_k: int = 10,
        feature_name: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for bugs related to a query.

        Args:
            query: Search query (e.g., "subscription payment")
            top_k: Number of results
            feature_name: Filter by feature name
            priority: Filter by priority (P0, P1, P2)
            category: Filter by category

        Returns:
            List of matching bugs with scores
        """
        # Generate query embedding
        query_embedding = self.embedder.embed_single(query)

        # Build filter
        filter_dict = {}
        if feature_name:
            filter_dict["feature_name"] = feature_name
        if priority:
            filter_dict["priority"] = priority
        if category:
            filter_dict["category"] = category

        filter_dict = filter_dict if filter_dict else None

        # Search
        results = self.store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_dict=filter_dict,
            score_threshold=0.25,
        )

        # Format results
        formatted = []
        for result in results:
            bug = result.get("metadata", {})
            bug["score"] = result.get("score", 0)
            bug["text"] = result.get("text", "")
            formatted.append(bug)

        return formatted

    def get_bugs_context(
        self,
        feature: str,
        top_k: int = 8,
        include_examples: bool = True,
    ) -> str:
        """Get bugs context for test generation.

        Args:
            feature: Feature name or description
            top_k: Number of bugs to include
            include_examples: Include example test assertions

        Returns:
            Formatted context string for LLM
        """
        bugs = self.search_bugs(feature, top_k=top_k)

        if not bugs:
            return ""

        context_parts = []
        context_parts.append("## KNOWN BUG PATTERNS (From Historical Bugs Database)\n")
        context_parts.append(
            "Before generating tests, our bugs database found these patterns "
            "for similar features:\n"
        )

        for i, bug in enumerate(bugs, 1):
            context_parts.append(f"### BUG-{i}: {bug.get('title', 'Unknown')}")
            context_parts.append(f"- **Feature**: {bug.get('feature_name', 'Unknown')}")
            context_parts.append(f"- **Category**: {bug.get('category', 'Unknown')}")
            context_parts.append(f"- **Priority**: {bug.get('priority', 'P2')}")
            context_parts.append(f"- **Status**: {bug.get('status', 'Unknown')}")

            if bug.get("expected"):
                context_parts.append(f"- **Expected**: {bug.get('expected')}")
            if bug.get("actual"):
                context_parts.append(f"- **Actual**: {bug.get('actual')}")
            if bug.get("root_cause"):
                context_parts.append(f"- **Root Cause**: {bug.get('root_cause')}")
            if bug.get("screen"):
                context_parts.append(f"- **Screen**: {bug.get('screen')}")

            # Add example test assertion
            if include_examples:
                context_parts.append("- **Suggested Test**: Verify this bug is caught by testing:")
                self._add_test_suggestion(context_parts, bug)

            context_parts.append("")

        # Add summary guidance
        context_parts.append("\n## HOW TO USE THIS INFORMATION\n")
        context_parts.append(
            "Generate tests that would CATCH these types of bugs:\n"
            "- Negative assertions (verify X does NOT appear when it shouldn't)\n"
            "- Navigation correctness (verify goes to RIGHT page, NOT wrong page)\n"
            "- State-specific behavior (subscribed user vs free user)\n"
            "- Validation gaps (missing required fields, boundary values)\n"
            "- Cross-feature propagation (wallet balance, subscription state)\n"
        )

        return "\n".join(context_parts)

    def _add_test_suggestion(self, parts: List[str], bug: Dict) -> None:
        """Add a test suggestion based on bug pattern."""
        category = bug.get("category", "")
        title = bug.get("title", "").lower()

        if category == "Navigation":
            parts.append(
                "  - Assert correct navigation destination (NOT incorrect redirect)"
            )
        elif category == "Subscription" or "subscri" in title:
            parts.append(
                "  - Assert behavior differs correctly for subscribed vs free users"
            )
        elif category == "UI/Visual":
            parts.append("  - Assert UI element visibility/invisibility based on state")
        elif category == "API":
            parts.append("  - Assert API response handling for both success and failure")
        elif "wallet" in title or "balance" in title:
            parts.append(
                "  - Assert wallet balance changes only when appropriate"
            )
        elif "popup" in title or "strip" in title:
            parts.append(
                "  - Assert popup/strip visibility based on user state"
            )
        else:
            parts.append("  - Assert the reported issue does not occur")

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            stats = self.store.get_stats()

            # Add bug-specific stats
            return {
                "collection": self.COLLECTION_NAME,
                "total_bugs": stats.get("points_count", 0),
                "status": stats.get("status", "unknown"),
            }
        except Exception as e:
            return {"collection": self.COLLECTION_NAME, "status": "error", "error": str(e)}

    def check_duplicate_file(self, source_file: str) -> Dict[str, Any]:
        """Check if a source file has already been uploaded.

        Args:
            source_file: The source CSV filename to check

        Returns:
            Dict with exists flag and count if exists
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Search for bugs with this source file
            response = self.store.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=1,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="source_file", match=MatchValue(value=source_file)
                        )
                    ]
                ),
                with_payload=True,
            )

            points = response[0]
            if points:
                # File exists, get count
                count_response = self.store.client.count(
                    collection_name=self.COLLECTION_NAME,
                    count_filter=Filter(
                        must=[
                            FieldCondition(
                                key="source_file", match=MatchValue(value=source_file)
                            )
                        ]
                    ),
                )
                return {
                    "exists": True,
                    "source_file": source_file,
                    "bug_count": count_response.count,
                    "feature_name": points[0].payload.get("feature_name", "Unknown"),
                }

            return {"exists": False, "source_file": source_file}

        except Exception as e:
            logger.error(f"Error checking duplicate file: {e}")
            return {"exists": False, "source_file": source_file, "error": str(e)}

    def get_bugs_by_feature(self) -> Dict[str, Dict[str, Any]]:
        """Get bug counts grouped by feature.

        Returns:
            Dict mapping feature_name to bug counts
        """
        # This is a workaround since Qdrant doesn't have native aggregation
        # We'll search with a broad query and aggregate locally
        try:

            # Scroll through all bugs
            all_bugs = []
            offset = None

            while True:
                response = self.store.client.scroll(
                    collection_name=self.COLLECTION_NAME,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                )

                points = response[0]
                if not points:
                    break

                for point in points:
                    all_bugs.append(point.payload)

                offset = response[1]  # Next offset
                if offset is None:
                    break

            # Aggregate by feature
            by_feature = {}
            for bug in all_bugs:
                feature = bug.get("feature_name", "Unknown")
                if feature not in by_feature:
                    by_feature[feature] = {
                        "total": 0,
                        "p0": 0,
                        "p1": 0,
                        "p2": 0,
                        "by_category": {},
                        "by_status": {},
                        "source_files": set(),
                    }

                by_feature[feature]["total"] += 1
                priority = bug.get("priority", "P2")
                if priority == "P0":
                    by_feature[feature]["p0"] += 1
                elif priority == "P1":
                    by_feature[feature]["p1"] += 1
                else:
                    by_feature[feature]["p2"] += 1

                category = bug.get("category", "Unknown")
                by_feature[feature]["by_category"][category] = (
                    by_feature[feature]["by_category"].get(category, 0) + 1
                )

                status = bug.get("status", "Unknown")
                by_feature[feature]["by_status"][status] = (
                    by_feature[feature]["by_status"].get(status, 0) + 1
                )

                source_file = bug.get("source_file", "")
                if source_file:
                    by_feature[feature]["source_files"].add(source_file)

            # Convert sets to lists for JSON serialization
            for feature in by_feature:
                by_feature[feature]["source_files"] = list(
                    by_feature[feature]["source_files"]
                )

            return by_feature

        except Exception as e:
            logger.error(f"Error aggregating bugs by feature: {e}")
            return {}

    def get_all_bugs(
        self,
        feature_name: Optional[str] = None,
        source_file: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get all bugs with optional filters.

        Args:
            feature_name: Filter by feature name
            source_file: Filter by source CSV file
            limit: Max bugs to return
            offset: Pagination offset

        Returns:
            List of bug documents
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Build filter
            conditions = []
            if feature_name:
                conditions.append(
                    FieldCondition(key="feature_name", match=MatchValue(value=feature_name))
                )
            if source_file:
                conditions.append(
                    FieldCondition(key="source_file", match=MatchValue(value=source_file))
                )

            qdrant_filter = Filter(must=conditions) if conditions else None

            # Scroll through bugs
            response = self.store.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=limit,
                offset=str(offset) if offset else None,
                scroll_filter=qdrant_filter,
                with_payload=True,
            )

            bugs = []
            for point in response[0]:
                bug = point.payload
                bug["id"] = str(point.id)
                bugs.append(bug)

            return bugs

        except Exception as e:
            logger.error(f"Error getting bugs: {e}")
            return []

    def delete_bugs_by_file(self, source_file: str) -> Dict[str, Any]:
        """Delete all bugs from a specific source file.

        Args:
            source_file: The source CSV filename

        Returns:
            Deletion stats
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Delete by filter
            self.store.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="source_file", match=MatchValue(value=source_file)
                        )
                    ]
                ),
            )

            return {"status": "success", "deleted_file": source_file}

        except Exception as e:
            logger.error(f"Error deleting bugs: {e}")
            return {"status": "error", "error": str(e)}

    def clear_all(self) -> Dict[str, Any]:
        """Clear all bugs from the collection."""
        try:
            self.store.delete_collection()
            # Recreate empty collection
            self.store = QdrantStore(
                collection_name=self.COLLECTION_NAME,
                host=self.store.host,
                port=self.store.port,
                dimension=self.embedder.dimension,
            )
            return {"status": "success", "message": "All bugs cleared"}
        except Exception as e:
            logger.error(f"Error clearing bugs: {e}")
            return {"status": "error", "error": str(e)}
