"""
RAG Integration for Test Case Intelligence System

This module provides RAG (Retrieval Augmented Generation) capabilities for the
test case generation pipeline. It indexes generated test cases, PRDs, and coverage
gaps in Qdrant vector database, and retrieves similar test patterns to enhance
future test generation.

Key Features:
- Store test cases, PRDs, and Figma data in Qdrant
- Retrieve similar test cases from past projects
- Learn from coverage gaps over time
- Auto-detect feature types for template suggestions
- Graceful degradation when Qdrant unavailable

Usage:
    rag = TestCaseRAG()

    # Index a test generation session (background task)
    stats = await rag.index_session(
        test_cases=test_cases,
        checklist=checklist,
        prd_content=prd_text,
        session_id=uuid.uuid4()
    )

    # Retrieve similar tests for new feature
    similar = rag.get_similar_tests("payment recharge", feature_type="payment")

    # Get RAG statistics
    stats = rag.get_rag_stats()
"""

import hashlib
import json
import logging
import os
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from rag import SimpleRAG, QdrantStore, EmbeddingProvider
from framework.models import TestCase, TestChecklist, CoverageAnalysis

logger = logging.getLogger(__name__)


# ============================================================================
# Feature Type Detection Patterns
# ============================================================================

FEATURE_TYPE_PATTERNS = {
    "payment": [
        "payment", "recharge", "transaction", "wallet", "coin", "upi", "card",
        "pay", "purchase", "checkout", "razorpay", "stripe", "debit", "credit"
    ],
    "auth": [
        "login", "signup", "password", "otp", "authentication", "verify",
        "register", "sign in", "sign up", "logout", "session", "token"
    ],
    "subscription": [
        "subscription", "plan", "subscribe", "premium", "trial", "renew",
        "upgrade", "downgrade", "tier", "membership", "pro", "plus"
    ],
    "navigation": [
        "navigate", "route", "screen", "back button", "menu", "drawer",
        "tab", "navigation", "redirect", "deeplink", "routing"
    ],
    "ui": [
        "design", "figma", "layout", "color", "padding", "spacing", "visual",
        "css", "style", "theme", "font", "icon", "button", "animation"
    ],
    "api": [
        "api", "endpoint", "request", "response", "fetch", "post", "get",
        "rest", "graphql", "axios", "http", "status code", "error"
    ],
    "data_sync": [
        "sync", "refresh", "real-time", "update", "websocket", "polling",
        "background sync", "offline", "cache", "stale data"
    ],
    "notification": [
        "notification", "push", "alert", "toast", "banner", "badge",
        "in-app notification", "firebase", "fcm", "silent push"
    ],
    "chat": [
        "chat", "message", "conversation", "reply", "send", "receive",
        "messaging", "dm", "inbox", "thread"
    ],
}


# ============================================================================
# Main RAG Integration Class
# ============================================================================

class TestCaseRAG:
    """
    RAG integration for intelligent test case generation.

    Manages four Qdrant collections:
    1. test_cases_v1: Individual test case documents
    2. prd_documents_v1: Chunked PRD content
    3. coverage_insights_v1: Coverage gaps and missing scenarios
    4. zk_config_docs: ZK app configuration documentation
    """

    def __init__(
        self,
        qdrant_host: Optional[str] = None,
        qdrant_port: Optional[int] = None,
        openai_api_key: Optional[str] = None,
    ):
        """
        Initialize TestCaseRAG.

        Args:
            qdrant_host: Qdrant host (defaults to env var or localhost)
            qdrant_port: Qdrant port (defaults to env var or 6335)
            openai_api_key: OpenAI API key for embeddings
        """
        # Get config from environment if not provided
        self.qdrant_host = qdrant_host or os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = qdrant_port or int(os.getenv("QDRANT_PORT", "6335"))

        # Initialize embedding provider
        self.embedder = EmbeddingProvider(
            provider="openai",
            api_key=openai_api_key or os.getenv("OPENAI_API_KEY"),
        )

        # Initialize RAG instances for each collection
        try:
            self.test_cases_rag = SimpleRAG(
                collection_name="test_cases_v1",
                qdrant_host=self.qdrant_host,
                qdrant_port=self.qdrant_port,
                embedding_provider="openai",
                openai_api_key=openai_api_key,
            )

            self.prd_rag = SimpleRAG(
                collection_name="prd_documents_v1",
                qdrant_host=self.qdrant_host,
                qdrant_port=self.qdrant_port,
                embedding_provider="openai",
                openai_api_key=openai_api_key,
            )

            self.coverage_rag = SimpleRAG(
                collection_name="coverage_insights_v1",
                qdrant_host=self.qdrant_host,
                qdrant_port=self.qdrant_port,
                embedding_provider="openai",
                openai_api_key=openai_api_key,
            )

            self.zk_config_rag = SimpleRAG(
                collection_name="zk_config_docs",
                qdrant_host=self.qdrant_host,
                qdrant_port=self.qdrant_port,
                embedding_provider="openai",
                openai_api_key=openai_api_key,
            )

            # Live ZK config collection (from ZK-Web)
            self.zk_live_rag = SimpleRAG(
                collection_name="zk_live_config",
                qdrant_host=self.qdrant_host,
                qdrant_port=self.qdrant_port,
                embedding_provider="openai",
                openai_api_key=openai_api_key,
            )

            # Truth Table entries collection
            self.truth_table_rag = SimpleRAG(
                collection_name="truth_table_v1",
                qdrant_host=self.qdrant_host,
                qdrant_port=self.qdrant_port,
                embedding_provider="openai",
                openai_api_key=openai_api_key,
            )

            self.enabled = self._check_qdrant_health()

            if self.enabled:
                logger.info("TestCaseRAG initialized successfully")
            else:
                logger.warning("TestCaseRAG initialized but Qdrant unavailable - graceful degradation mode")

        except Exception as e:
            logger.error(f"Failed to initialize TestCaseRAG: {e}")
            self.enabled = False

    def _check_qdrant_health(self) -> bool:
        """
        Check if Qdrant is available and healthy.

        Returns:
            True if Qdrant is accessible, False otherwise
        """
        try:
            # Try to connect to Qdrant by checking collections
            self.test_cases_rag.store.client.get_collections()
            return True
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}")
            return False

    # ========================================================================
    # Indexing Methods
    # ========================================================================

    async def index_session(
        self,
        test_cases: List[TestCase],
        checklist: TestChecklist,
        prd_content: str,
        session_id: str,
        figma_data: Optional[Dict] = None,
        # NEW VERSION TRACKING PARAMS
        version: int = 1,
        documents_included: Optional[List[str]] = None,
        source_document: str = "prd",
        test_scope: str = "frontend",
    ) -> Dict[str, Any]:
        """
        Index a complete test generation session in RAG.

        This is typically called as a background task after test case generation
        is complete, so it doesn't block the user.

        Args:
            test_cases: List of generated test cases
            checklist: Test checklist with coverage analysis
            prd_content: Original PRD text content
            session_id: Unique session identifier (format: FeatureName_V1)
            figma_data: Optional Figma design data
            version: Version number (default 1)
            documents_included: List of documents ["prd", "frontend_lld", "backend_lld", "figma"]
            source_document: Which document generated these tests
            test_scope: "frontend" or "backend"

        Returns:
            Dictionary with indexing statistics
        """
        if not self.enabled:
            logger.warning("RAG not enabled, skipping indexing")
            return {
                "status": "skipped",
                "reason": "qdrant_unavailable",
                "test_cases": 0,
                "prd_chunks": 0,
                "coverage_gaps": 0,
            }

        stats = {
            "status": "success",
            "session_id": session_id,
            "test_cases": 0,
            "prd_chunks": 0,
            "coverage_gaps": 0,
            "indexed_at": datetime.now().isoformat(),
        }

        # Default documents_included if not provided
        if documents_included is None:
            documents_included = ["prd"]

        try:
            # Index test cases with version metadata
            logger.info(f"Indexing {len(test_cases)} test cases for session {session_id} (v{version})")
            test_case_count = await self._index_test_cases(
                test_cases,
                session_id,
                checklist,
                version=version,
                documents_included=documents_included,
                source_document=source_document,
                test_scope=test_scope,
            )
            stats["test_cases"] = test_case_count
            stats["version"] = version
            stats["documents_included"] = documents_included
            stats["test_scope"] = test_scope

            # Index PRD content
            logger.info(f"Indexing PRD content for session {session_id}")
            prd_chunk_count = await self._index_prd_content(
                prd_content,
                session_id,
                checklist.feature_name
            )
            stats["prd_chunks"] = prd_chunk_count

            # Index coverage gaps (use getattr for backend checklist compatibility)
            coverage_analysis = getattr(checklist, 'coverage_analysis', None)
            if coverage_analysis:
                logger.info(f"Indexing coverage gaps for session {session_id}")
                gap_count = await self._index_coverage_gaps(
                    coverage_analysis,
                    session_id,
                    checklist.feature_name
                )
                stats["coverage_gaps"] = gap_count

            # Index truth table entries if available
            truth_table_entries = getattr(checklist, 'truth_table_entries', None)
            if truth_table_entries:
                logger.info(f"Indexing {len(truth_table_entries)} truth table entries for session {session_id}")
                truth_table_count = await self._index_truth_table(
                    truth_table_entries,
                    session_id,
                    checklist.feature_name,
                    version=version,
                    documents_included=documents_included,
                )
                stats["truth_table_entries"] = truth_table_count

            logger.info(f"Session indexing complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error indexing session {session_id}: {e}")
            stats["status"] = "error"
            stats["error_message"] = str(e)
            return stats

    async def _index_test_cases(
        self,
        test_cases: List[TestCase],
        session_id: str,
        checklist: TestChecklist,
        version: int = 1,
        documents_included: Optional[List[str]] = None,
        source_document: str = "prd",
        test_scope: str = "frontend",
    ) -> int:
        """
        Index test cases into test_cases_v1 collection with deduplication.

        Each test case becomes one document with:
        - Embedding from: requirement + steps + expected result
        - Metadata: feature, priority, test_type, detected_feature_type, version, etc.

        Deduplication:
        - Uses test_case_id as unique identifier
        - Skips test cases that already exist with same ID and session
        - Updates existing test cases if content has changed

        Args:
            test_cases: List of TestCase objects
            session_id: Session identifier (format: FeatureName_V1)
            checklist: TestChecklist for coverage score
            version: Version number
            documents_included: List of source documents
            source_document: Which document generated this test
            test_scope: "frontend" or "backend"

        Returns:
            Number of test cases indexed (excluding duplicates)
        """
        if not test_cases:
            return 0

        # Get existing test case IDs for this session to check for duplicates
        existing_ids = set()
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            query_filter = Filter(must=[
                FieldCondition(key="session_id", match=MatchValue(value=session_id))
            ])

            existing_points = self.test_cases_rag.store.client.scroll(
                collection_name=self.test_cases_rag.store.collection_name,
                scroll_filter=query_filter,
                limit=10000,
                with_payload=True,
            )[0]

            for point in existing_points:
                payload = point.payload or {}
                tc_id = payload.get("test_case_id", "")
                if tc_id:
                    existing_ids.add(tc_id)

            if existing_ids:
                logger.info(f"Found {len(existing_ids)} existing test cases for session {session_id}")
        except Exception as e:
            logger.warning(f"Could not check for existing test cases: {e}")

        texts = []
        metadata_list = []
        point_ids = []
        skipped_count = 0

        for tc in test_cases:
            # Skip if this test case ID already exists for this session (deduplication)
            if tc.test_case_id in existing_ids:
                skipped_count += 1
                continue

            # Build document text for embedding - use new format fields
            # Support both frontend TestCase and backend BackendTestCase formats
            test_scenario = getattr(tc, 'test_scenario', '') or getattr(tc, 'requirement_description', '')
            steps_to_execute = getattr(tc, 'steps_to_execute', '') or getattr(tc, 'test_step', '') or getattr(tc, 'verification_method', '')
            category = getattr(tc, 'category', '') or 'General Features'
            user_type = getattr(tc, 'user_type', '') or 'Any'
            screen_reference = getattr(tc, 'screen_reference', '') or ''
            precondition = getattr(tc, 'precondition', '') or ''
            # Support both frontend (feature) and backend (category) test cases
            feature = getattr(tc, 'feature', None) or getattr(tc, 'category', '') or 'General'
            # For backend, also include api_component if available
            api_component = getattr(tc, 'api_component', '')

            # Derive api_component if empty (for backend test cases)
            if not api_component and hasattr(tc, 'test_type'):
                test_type = tc.test_type or ''
                if test_type == "Database":
                    api_component = "Database"
                elif test_type == "Security":
                    api_component = "Security Module"
                elif test_type == "Integration":
                    api_component = "Integration Layer"
                elif test_type == "Performance":
                    api_component = "Performance Module"
                elif test_type == "API":
                    api_component = "API Endpoint"
                elif category:
                    # Use category as fallback
                    api_component = category.replace("-", " ").title()
                else:
                    api_component = "Backend Service"

            doc_text = f"""
Feature: {feature}
Priority: {tc.priority}
Category: {category}
User Type: {user_type}
Type: {tc.test_type or 'general'}
{f'API Component: {api_component}' if api_component else ''}

Test Scenario: {test_scenario}

Steps to Execute: {steps_to_execute}

Expected Result: {tc.expected_result}

Screen Reference: {screen_reference}
Precondition: {precondition}
            """.strip()

            texts.append(doc_text)

            # Build metadata
            # Detect feature type from content
            feature_type = self._detect_feature_type(tc)

            # Extract user states mentioned in test
            user_states = self._extract_user_states(tc)

            # Extract screens mentioned in test
            screens = self._extract_screens(tc)

            metadata = {
                # Identifiers
                "doc_type": "test_case",
                "test_case_id": tc.test_case_id,
                "session_id": session_id,

                # Core identification (new format)
                "priority": tc.priority,
                "category": category,
                "user_type": user_type,

                # Context fields (new format)
                "screen_reference": screen_reference[:200] if screen_reference else "",
                "precondition": precondition[:300] if precondition else "",

                # Test definition (new format - "Verify that..." style)
                "test_scenario": test_scenario[:500],  # Must start with "Verify that..."
                "steps_to_execute": steps_to_execute[:1000],  # Numbered steps
                "expected_result": tc.expected_result[:500] if tc.expected_result else "",

                # Status tracking (new format)
                "dev_status": getattr(tc, 'dev_status', 'Not Started'),
                "qa_status": getattr(tc, 'qa_status', 'Not Started'),
                "comments": getattr(tc, 'comments', '')[:300] if getattr(tc, 'comments', '') else "",

                # Legacy fields for backward compatibility
                "feature": feature,  # Use computed feature (supports both frontend and backend)
                "test_type": tc.test_type or "general",
                "api_component": api_component,  # Backend-specific field
                "requirement_description": test_scenario[:500],  # Alias for test_scenario
                "test_step": steps_to_execute[:1000],  # Alias for steps_to_execute

                # Detected/extracted intelligence
                "feature_type_detected": feature_type,
                "user_states": user_states,
                "screens_involved": screens,

                # Context
                "coverage_score": checklist.coverage_score,
                "generated_at": datetime.now().isoformat(),

                # VERSION TRACKING (new fields for feature versioning)
                "version": version,
                "documents_included": documents_included or ["prd"],
                "source_document": source_document,
                "test_scope": test_scope,
                "last_updated": datetime.now().isoformat(),
            }

            # Optional fields (use getattr for backend compatibility)
            screenshot_url = getattr(tc, 'screenshot_url', None)
            if screenshot_url:
                metadata["screenshot_url"] = screenshot_url

            # Generate unique point ID for this test case (prevents cross-session collisions)
            point_id = hashlib.md5(f"{session_id}_{tc.test_case_id}".encode()).hexdigest()
            point_ids.append(point_id)

            texts.append(doc_text)
            metadata_list.append(metadata)

        # Log deduplication stats
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} duplicate test cases for session {session_id}")

        # Only proceed if we have new test cases to index
        if not texts:
            logger.info(f"No new test cases to index for session {session_id} (all {skipped_count} were duplicates)")
            return 0

        # Generate embeddings
        embeddings = self.embedder.embed(texts)

        # Store in Qdrant with unique point IDs
        self.test_cases_rag.store.add_documents(
            texts=texts,
            embeddings=embeddings,
            metadata=metadata_list,
            ids=point_ids,
        )

        indexed_count = len(texts)
        logger.info(f"Indexed {indexed_count} test cases (skipped {skipped_count} duplicates)")
        return indexed_count

    async def _index_prd_content(
        self,
        prd_content: str,
        session_id: str,
        feature_name: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> int:
        """
        Index PRD content into prd_documents_v1 collection.

        Chunks the PRD text and creates searchable documents.

        Args:
            prd_content: PRD text content
            session_id: Session identifier
            feature_name: Feature name from analysis
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks

        Returns:
            Number of chunks indexed
        """
        if not prd_content or len(prd_content.strip()) == 0:
            return 0

        # Chunk the PRD text
        chunks = self._chunk_text(prd_content, chunk_size, chunk_overlap)

        metadata_list = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "doc_type": "prd",
                "session_id": session_id,
                "feature_name": feature_name,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "indexed_at": datetime.now().isoformat(),
            }
            metadata_list.append(metadata)

        # Generate embeddings
        embeddings = self.embedder.embed(chunks)

        # Store in Qdrant
        self.prd_rag.store.add_documents(chunks, embeddings, metadata_list)

        logger.info(f"Indexed {len(chunks)} PRD chunks")
        return len(chunks)

    async def _index_truth_table(
        self,
        truth_table_entries: List,
        session_id: str,
        feature_name: str,
        version: int = 1,
        documents_included: Optional[List[str]] = None,
    ) -> int:
        """
        Index truth table entries into truth_table_v1 collection.

        Each truth table entry becomes one document with:
        - Embedding from: screen + checkpoint + expected
        - Metadata: feature, priority, test_type, redirects, etc.

        Args:
            truth_table_entries: List of TruthTableEntry objects
            session_id: Session identifier (format: FeatureName_V1)
            feature_name: Feature name
            version: Version number
            documents_included: List of source documents

        Returns:
            Number of truth table entries indexed
        """
        if not truth_table_entries:
            return 0

        texts = []
        metadata_list = []

        for entry in truth_table_entries:
            # Build document text for embedding
            doc_text = f"""
Screen: {entry.screen}
Checkpoint: {entry.checkpoint}
Feature: {entry.feature}
Priority: {entry.priority}
Test Type: {entry.test_type}

Failed Redirect: {entry.failed_redirect}
Pending Redirect: {entry.pending_redirect}
Successful Redirect: {entry.successful_redirect}

Expected: {entry.expected}
            """.strip()

            texts.append(doc_text)

            # Build metadata
            metadata = {
                "doc_type": "truth_table_entry",
                "entry_id": entry.id,
                "session_id": session_id,
                "feature_name": feature_name,
                "screen": entry.screen,
                "checkpoint": entry.checkpoint[:500] if entry.checkpoint else "",
                "failed_redirect": entry.failed_redirect,
                "pending_redirect": entry.pending_redirect,
                "successful_redirect": entry.successful_redirect,
                "auto_redirect_failed": entry.auto_redirect_failed,
                "auto_redirect_pending": entry.auto_redirect_pending,
                "auto_redirect_success": entry.auto_redirect_success,
                "result": entry.result,
                "expected": entry.expected[:500] if entry.expected else "",
                "feature": entry.feature,
                "priority": entry.priority,
                "test_type": entry.test_type,
                "version": version,
                "documents_included": documents_included or ["prd"],
                "generated_at": datetime.now().isoformat(),
            }

            metadata_list.append(metadata)

        # Generate embeddings
        embeddings = self.embedder.embed(texts)

        # Store in Qdrant
        self.truth_table_rag.store.add_documents(texts, embeddings, metadata_list)

        logger.info(f"Indexed {len(truth_table_entries)} truth table entries")
        return len(truth_table_entries)

    async def _index_coverage_gaps(
        self,
        coverage_analysis: CoverageAnalysis,
        session_id: str,
        feature_name: str,
    ) -> int:
        """
        Index coverage gaps into coverage_insights_v1 collection.

        Stores missing test scenarios for learning over time.

        Args:
            coverage_analysis: Coverage analysis from checklist
            session_id: Session identifier
            feature_name: Feature name

        Returns:
            Number of gaps indexed
        """
        if not coverage_analysis.missing_scenarios:
            return 0

        texts = []
        metadata_list = []

        # Get feature types from high-risk features
        feature_type = "general"
        if coverage_analysis.risk_assessment.high_risk_features:
            # Try to detect from feature name
            test_case_mock = type('obj', (object,), {
                'requirement_description': feature_name,
                'test_step': ' '.join(coverage_analysis.missing_scenarios[:3])
            })()
            feature_type = self._detect_feature_type(test_case_mock)

        for scenario in coverage_analysis.missing_scenarios:
            text = f"Missing test scenario for {feature_name}: {scenario}"
            texts.append(text)

            metadata = {
                "doc_type": "coverage_gap",
                "session_id": session_id,
                "feature_name": feature_name,
                "feature_type": feature_type,
                "missing_scenario": scenario,
                "detected_at": datetime.now().isoformat(),
            }
            metadata_list.append(metadata)

        # Generate embeddings
        embeddings = self.embedder.embed(texts)

        # Store in Qdrant
        self.coverage_rag.store.add_documents(texts, embeddings, metadata_list)

        logger.info(f"Indexed {len(texts)} coverage gaps")
        return len(texts)

    # ========================================================================
    # ZK Config Documentation Methods
    # ========================================================================

    async def index_zk_config(
        self,
        config_content: str,
        doc_name: str = "ZK_CONFIG_BEHAVIOR_GUIDE",
        also_index_as_prd: bool = True,
        chunk_size: int = 1500,
        chunk_overlap: int = 300,
    ) -> Dict[str, Any]:
        """
        Index ZK Config documentation into dedicated collection and optionally PRD collection.

        Args:
            config_content: The ZK Config markdown content
            doc_name: Document name for metadata
            also_index_as_prd: Whether to also index in prd_documents_v1
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks

        Returns:
            Dictionary with indexing statistics
        """
        if not self.enabled:
            logger.warning("RAG not enabled, skipping ZK Config indexing")
            return {
                "status": "skipped",
                "reason": "qdrant_unavailable",
                "zk_config_chunks": 0,
                "prd_chunks": 0,
            }

        stats = {
            "status": "success",
            "doc_name": doc_name,
            "zk_config_chunks": 0,
            "prd_chunks": 0,
            "indexed_at": datetime.now().isoformat(),
        }

        try:
            # Parse sections from markdown
            sections = self._parse_config_sections(config_content)
            logger.info(f"Parsed {len(sections)} sections from ZK Config")

            # Index into zk_config_docs collection
            zk_chunks = await self._index_config_sections(sections, doc_name)
            stats["zk_config_chunks"] = zk_chunks

            # Also index into prd_documents_v1 for general retrieval
            if also_index_as_prd:
                prd_chunks = await self._index_prd_content(
                    config_content,
                    session_id=f"zk_config_{doc_name}",
                    feature_name="ZK App Configuration",
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                stats["prd_chunks"] = prd_chunks

            logger.info(f"ZK Config indexing complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error indexing ZK Config: {e}")
            stats["status"] = "error"
            stats["error_message"] = str(e)
            return stats

    def _parse_config_sections(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse ZK Config markdown into sections by config key.

        Args:
            content: Markdown content

        Returns:
            List of section dictionaries with config_key, title, content, category
        """
        sections = []
        current_category = "General"
        current_section = None

        lines = content.split('\n')

        for line in lines:
            # Detect category headers (## headers)
            if line.startswith('## ') and not line.startswith('### '):
                current_category = line[3:].strip()
                continue

            # Detect config key headers (### `configKey` or ### configKey)
            if line.startswith('### '):
                # Save previous section
                if current_section:
                    sections.append(current_section)

                # Extract config key
                title = line[4:].strip()
                config_key = title.strip('`').split('/')[0].split(' ')[0]

                current_section = {
                    "config_key": config_key,
                    "title": title,
                    "category": current_category,
                    "content": "",
                }
                continue

            # Add content to current section
            if current_section:
                current_section["content"] += line + "\n"

        # Don't forget last section
        if current_section:
            sections.append(current_section)

        return sections

    async def _index_config_sections(
        self,
        sections: List[Dict[str, Any]],
        doc_name: str,
    ) -> int:
        """
        Index config sections into zk_config_docs collection.

        Args:
            sections: Parsed config sections
            doc_name: Document name

        Returns:
            Number of sections indexed
        """
        if not sections:
            return 0

        texts = []
        metadata_list = []

        for section in sections:
            # Build searchable text
            doc_text = f"""
Config Key: {section['config_key']}
Category: {section['category']}
Title: {section['title']}

{section['content'].strip()}
            """.strip()

            texts.append(doc_text)

            metadata = {
                "doc_type": "zk_config",
                "config_key": section["config_key"],
                "category": section["category"],
                "title": section["title"],
                "doc_name": doc_name,
                "indexed_at": datetime.now().isoformat(),
            }
            metadata_list.append(metadata)

        # Generate embeddings
        embeddings = self.embedder.embed(texts)

        # Store in Qdrant
        self.zk_config_rag.store.add_documents(texts, embeddings, metadata_list)

        logger.info(f"Indexed {len(sections)} ZK Config sections")
        return len(sections)

    def get_config_context(
        self,
        query: str,
        category_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant ZK Config documentation for a query.

        Args:
            query: Search query (e.g., "payment configuration", "chat streaming")
            category_filter: Optional filter by category (e.g., "Payment & Wallet")
            top_k: Number of results to return

        Returns:
            List of relevant config sections with metadata
        """
        if not self.enabled:
            logger.warning("RAG not enabled, returning empty config context")
            return []

        try:
            query_embedding = self.zk_config_rag.embedder.embed_single(query)

            # Build filter
            filter_dict = None
            if category_filter:
                filter_dict = {"category": category_filter}

            # Search
            results = self.zk_config_rag.store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_dict=filter_dict,
                score_threshold=0.1,
            )

            return results

        except Exception as e:
            logger.error(f"Error retrieving config context: {e}", exc_info=True)
            return []

    def format_config_context(
        self,
        config_results: List[Dict[str, Any]],
    ) -> str:
        """
        Format retrieved ZK Config documentation as context for LLM prompt.

        Args:
            config_results: List of config search results

        Returns:
            Formatted markdown context string
        """
        if not config_results:
            return ""

        context_parts = ["## ZK App Configuration Reference\n"]
        context_parts.append("The following configuration settings are relevant to this feature:\n")

        for result in config_results:
            metadata = result.get("metadata", {})
            text = result.get("text", "")
            score = result.get("score", 0)

            context_parts.append(f"### {metadata.get('config_key', 'Unknown')} ({metadata.get('category', 'General')})")
            context_parts.append(f"*Relevance: {score*100:.0f}%*\n")

            # Include truncated content
            content_preview = text[:800] + "..." if len(text) > 800 else text
            context_parts.append(content_preview)
            context_parts.append("")

        context_parts.append("\n**Use this configuration context to:**")
        context_parts.append("- Generate test cases that cover config-dependent behavior")
        context_parts.append("- Include edge cases for different config values")
        context_parts.append("- Test version-specific feature flags")
        context_parts.append("- Validate UI behavior based on config settings\n")

        return "\n".join(context_parts)

    # ========================================================================
    # Structured Config Documentation Methods (NEW)
    # ========================================================================

    async def index_zk_config_docs(
        self,
        docs: List[Dict[str, Any]],
    ) -> int:
        """
        Index structured config documentation from ZKConfigBehaviorParser.

        Each doc contains:
        - config_name: The config key name
        - category: Category grouping
        - config_type: boolean, string, number, etc.
        - description: Short description
        - behavioral_impact: Detailed impact text
        - examples: List of {value, effect} dicts
        - implementation_ref: File:line reference
        - embedding_text: Pre-computed text for embedding

        Args:
            docs: List of config doc dictionaries

        Returns:
            Number of documents indexed
        """
        if not self.enabled:
            logger.warning("RAG not enabled, skipping config docs indexing")
            return 0

        try:
            # Delete existing docs to avoid duplicates
            try:
                self.zk_config_rag.store.delete_collection()
                logger.info("Deleted existing zk_config_docs collection")
            except Exception:
                pass

            # Recreate collection
            self.zk_config_rag.store._init_client()

            # Prepare texts and metadata
            texts = []
            metadatas = []

            for doc in docs:
                # Use the embedding text for search
                text = doc.get("embedding_text", "")
                if not text:
                    text = f"{doc.get('config_name', '')} {doc.get('description', '')} {doc.get('behavioral_impact', '')}"

                texts.append(text)
                metadatas.append({
                    "config_name": doc.get("config_name", ""),
                    "category": doc.get("category", ""),
                    "config_type": doc.get("config_type", "unknown"),
                    "description": doc.get("description", ""),
                    "behavioral_impact": doc.get("behavioral_impact", ""),
                    "implementation_ref": doc.get("implementation_ref", ""),
                    "default_value": doc.get("default_value", ""),
                    "examples": json.dumps(doc.get("examples", [])[:5]),  # Store as JSON string
                    "related_configs": json.dumps(doc.get("related_configs", [])),
                    "indexed_at": datetime.now().isoformat(),
                })

            # Generate embeddings
            embeddings = self.zk_config_rag.embedder.embed(texts)

            # Index to Qdrant
            self.zk_config_rag.store.add_documents(
                texts=texts,
                embeddings=embeddings,
                metadata=metadatas,
            )

            logger.info(f"Indexed {len(docs)} config docs to zk_config_docs collection")
            return len(docs)

        except Exception as e:
            logger.error(f"Error indexing config docs: {e}", exc_info=True)
            return 0

    def get_config_behavior_context(
        self,
        query: str,
        category_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve config behavioral documentation for a query.

        This returns structured config documentation including:
        - What the config does
        - TRUE vs FALSE behavior (for booleans)
        - Examples with values and effects
        - Implementation references

        Args:
            query: Search query (e.g., "streaming chat", "payment")
            category_filter: Optional category filter
            top_k: Number of results

        Returns:
            List of config docs with full behavioral details
        """
        if not self.enabled:
            logger.warning("RAG not enabled, returning empty config behavior context")
            return []

        try:
            query_embedding = self.zk_config_rag.embedder.embed_single(query)

            # Build filter
            filter_dict = None
            if category_filter:
                filter_dict = {"category": category_filter}

            # Search
            results = self.zk_config_rag.store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_dict=filter_dict,
                score_threshold=0.1,
            )

            # Format results with full details
            formatted = []
            for result in results:
                metadata = result.get("metadata", {})

                # Parse JSON fields back to objects
                examples = []
                try:
                    examples = json.loads(metadata.get("examples", "[]"))
                except Exception:
                    pass

                related = []
                try:
                    related = json.loads(metadata.get("related_configs", "[]"))
                except Exception:
                    pass

                formatted.append({
                    "config_name": metadata.get("config_name", ""),
                    "category": metadata.get("category", ""),
                    "config_type": metadata.get("config_type", "unknown"),
                    "description": metadata.get("description", ""),
                    "behavioral_impact": metadata.get("behavioral_impact", ""),
                    "examples": examples,
                    "implementation_ref": metadata.get("implementation_ref", ""),
                    "default_value": metadata.get("default_value", ""),
                    "related_configs": related,
                    "score": result.get("score", 0),
                })

            return formatted

        except Exception as e:
            logger.error(f"Error retrieving config behavior context: {e}", exc_info=True)
            return []

    def format_config_behavior_context(
        self,
        config_results: List[Dict[str, Any]],
    ) -> str:
        """
        Format config behavioral docs as context for LLM test generation.

        This produces a prompt section that explains:
        - What each relevant config does
        - How behavior changes based on config values
        - Test cases that should be generated for each config

        Args:
            config_results: Results from get_config_behavior_context()

        Returns:
            Formatted markdown context for LLM prompt
        """
        if not config_results:
            return ""

        context_parts = ["## ZK CONFIG BEHAVIORS (Reference Only)\n"]
        context_parts.append("**IMPORTANT**: These configs are for REFERENCE. Only include config-specific test cases")
        context_parts.append("if the config DIRECTLY affects the feature being tested. Do NOT clutter test cases")
        context_parts.append("with config variations unless they are essential to the feature's core behavior.\n")
        context_parts.append("Relevant configurations:\n")

        # OPTIMIZED: Compact format to reduce context size
        for config in config_results[:3]:  # Max 3 configs
            config_name = config.get("config_name", "Unknown")
            config_type = config.get("config_type", "unknown")
            default_val = config.get("default_value", "")
            description = config.get("description", "")[:150]  # Truncate
            examples = config.get("examples", [])

            context_parts.append(f"• **{config_name}** ({config_type})")
            if default_val:
                context_parts.append(f"  Default: `{default_val}`")
            if description:
                context_parts.append(f"  {description}")
            # Only show 2 examples max
            if examples:
                for ex in examples[:2]:
                    value = ex.get("value", "")
                    effect = ex.get("effect", "")[:80]  # Truncate effect
                    if value and effect:
                        context_parts.append(f"  `{value}` → {effect}")
            context_parts.append("")

        context_parts.append("\n**Config Test Guidance:**")
        context_parts.append("- Only test config variations if the config DIRECTLY controls the feature")
        context_parts.append("- Default values are used in production 99% of the time - focus on default behavior")
        context_parts.append("- Config-specific tests are OPTIONAL - prioritize core feature functionality\n")

        return "\n".join(context_parts)

    # ========================================================================
    # Live ZK Config Methods
    # ========================================================================

    async def index_zk_live_configs(
        self,
        configs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Index live ZK configs from ZK-Web into RAG.

        Args:
            configs: List of config documents from zk_client.format_configs_for_indexing()

        Returns:
            Indexing statistics
        """
        if not self.enabled:
            return {
                "status": "skipped",
                "reason": "qdrant_unavailable",
                "configs_indexed": 0,
            }

        if not configs:
            return {
                "status": "skipped",
                "reason": "no_configs_provided",
                "configs_indexed": 0,
            }

        try:
            texts = []
            metadata_list = []
            ids = []

            for config in configs:
                texts.append(config["text"])
                metadata_list.append(config["metadata"])
                # Use path as unique ID
                config_id = config["metadata"]["path"].replace("/", "_")
                ids.append(f"zk_live_{config_id}")

            # Generate embeddings
            embeddings = self.zk_live_rag.embedder.embed(texts)

            # Store in Qdrant
            self.zk_live_rag.store.add_documents(
                texts=texts,
                embeddings=embeddings,
                metadata=metadata_list,
                ids=ids,
            )

            logger.info(f"Indexed {len(texts)} live ZK configs")

            return {
                "status": "success",
                "configs_indexed": len(texts),
                "indexed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error indexing live ZK configs: {e}", exc_info=True)
            return {
                "status": "error",
                "error_message": str(e),
                "configs_indexed": 0,
            }

    def get_live_config_context(
        self,
        query: str,
        category_filter: Optional[str] = None,
        path_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant live ZK configs for a query.

        Args:
            query: Search query (e.g., "payment gateway", "chat config")
            category_filter: Optional filter by category (e.g., "payments")
            path_filter: Optional filter by path prefix (e.g., "/myapp/payments")
            top_k: Number of results to return

        Returns:
            List of relevant live configs with metadata
        """
        if not self.enabled:
            logger.warning("RAG not enabled, returning empty live config context")
            return []

        try:
            query_embedding = self.zk_live_rag.embedder.embed_single(query)

            # Build filter
            filter_dict = None
            if category_filter:
                filter_dict = {"category": category_filter}

            # Search
            results = self.zk_live_rag.store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_dict=filter_dict,
                score_threshold=0.1,
            )

            # Additional path filtering if needed
            if path_filter:
                results = [
                    r for r in results
                    if r.get("metadata", {}).get("path", "").startswith(path_filter)
                ]

            return results

        except Exception as e:
            logger.error(f"Error retrieving live config context: {e}", exc_info=True)
            return []

    def format_live_config_context(
        self,
        config_results: List[Dict[str, Any]],
    ) -> str:
        """
        Format retrieved live ZK configs as context for LLM prompt.

        Args:
            config_results: List of live config search results

        Returns:
            Formatted markdown context string
        """
        if not config_results:
            return ""

        context_parts = ["## Live ZK Configuration Values\n"]
        context_parts.append("The following ACTUAL configuration values are in use:\n")

        for result in config_results:
            metadata = result.get("metadata", {})
            text = result.get("text", "")
            score = result.get("score", 0)

            context_parts.append(f"### {metadata.get('config_name', 'Unknown')} ({metadata.get('category', 'General')})")
            context_parts.append(f"**Path**: `{metadata.get('path', 'N/A')}`")
            context_parts.append(f"*Relevance: {score*100:.0f}%*\n")

            # Include the config data
            context_parts.append("```")
            context_parts.append(text)
            context_parts.append("```")
            context_parts.append("")

        context_parts.append("\n**Use these REAL config values to:**")
        context_parts.append("- Generate test cases with actual expected values")
        context_parts.append("- Validate edge cases based on real thresholds")
        context_parts.append("- Test country-specific behavior (IN, US, etc.)")
        context_parts.append("- Compare expected vs actual configuration\n")

        return "\n".join(context_parts)

    # ========================================================================
    # Retrieval Methods
    # ========================================================================

    def get_similar_tests(
        self,
        query: str,
        feature_type: Optional[str] = None,
        top_k: int = 5,
        priority_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar test cases from past projects.

        Uses semantic search with optional filtering and multi-factor ranking.

        Args:
            query: Search query (e.g., "payment recharge flow")
            feature_type: Optional filter by detected feature type
            top_k: Number of results to return
            priority_filter: Optional filter by priority (P0, P1, etc.)

        Returns:
            List of similar test cases with metadata and scores
        """
        if not self.enabled:
            logger.warning("RAG not enabled, returning empty results")
            return []

        try:
            # Search using get_context which works
            # Note: search() method has issues, so we use the working method
            query_embedding = self.test_cases_rag.embedder.embed_single(query)

            # Build filter for Qdrant
            filter_dict = None
            if feature_type or priority_filter:
                filter_dict = {}
                if feature_type:
                    filter_dict["feature_type_detected"] = feature_type
                if priority_filter:
                    filter_dict["priority"] = priority_filter

            # Search using store directly
            results = self.test_cases_rag.store.search(
                query_embedding=query_embedding,
                top_k=top_k * 2,  # Get 2x for ranking
                filter_dict=filter_dict,
                score_threshold=0.1,
            )

            # Filter by doc_type manually
            filtered_results = [
                r for r in results
                if r.get("metadata", {}).get("doc_type") == "test_case"
            ]

            # Rank results using multiple factors
            ranked_results = self._rank_test_results(filtered_results, query, feature_type)

            # Return top_k after ranking
            return ranked_results[:top_k]

        except Exception as e:
            logger.error(f"Error retrieving similar tests: {e}", exc_info=True)
            return []

    def get_common_gaps_for_feature(
        self,
        feature_type: str,
        top_k: int = 5,
    ) -> List[str]:
        """
        Get most frequently missing test scenarios for a feature type.

        This enables learning from historical coverage gaps.

        Args:
            feature_type: Feature type (payment, auth, etc.)
            top_k: Number of common gaps to return

        Returns:
            List of common missing scenarios
        """
        if not self.enabled:
            return []

        try:
            query = f"{feature_type} coverage gaps missing scenarios"
            query_embedding = self.coverage_rag.embedder.embed_single(query)

            # Search using store directly
            results = self.coverage_rag.store.search(
                query_embedding=query_embedding,
                top_k=20,
                score_threshold=0.1,
            )

            # Filter by feature type
            type_filtered = [
                r for r in results
                if r.get("metadata", {}).get("feature_type") == feature_type
            ]

            # Count scenario frequency
            scenario_counts = Counter()
            for result in type_filtered:
                scenario = result.get("metadata", {}).get("missing_scenario")
                if scenario:
                    scenario_counts[scenario] += 1

            # Return most common
            return [scenario for scenario, _ in scenario_counts.most_common(top_k)]

        except Exception as e:
            logger.error(f"Error getting common gaps: {e}", exc_info=True)
            return []

    def format_rag_context(
        self,
        similar_tests: List[Dict[str, Any]],
        include_gaps: bool = True,
        feature_type: Optional[str] = None,
    ) -> str:
        """
        Format retrieved test cases as context for LLM prompt.

        Args:
            similar_tests: List of similar test case results
            include_gaps: Whether to include common coverage gaps
            feature_type: Feature type for gap retrieval

        Returns:
            Formatted markdown context string
        """
        if not similar_tests and not include_gaps:
            return ""

        context_parts = []

        # Add similar test cases
        if similar_tests:
            context_parts.append("### Reference Test Cases from Similar Features\n")

            for i, test in enumerate(similar_tests, 1):
                metadata = test.get("metadata", {})
                score = test.get("score", 0)

                context_parts.append(f"**Example {i}**: {metadata.get('feature', 'Unknown')} "
                                   f"({metadata.get('test_type', 'general')}, "
                                   f"{metadata.get('priority', 'P2')}, "
                                   f"{metadata.get('coverage_score', 0):.0f}% coverage)")

                context_parts.append(f"- Requirement: {metadata.get('requirement_description', 'N/A')[:200]}...")

                if metadata.get('user_states'):
                    context_parts.append(f"- User States: {', '.join(metadata['user_states'])}")

                if metadata.get('screens_involved'):
                    context_parts.append(f"- Screens: {', '.join(metadata['screens_involved'][:3])}")

                context_parts.append(f"- Relevance: {score*100:.0f}%\n")

        # Add common coverage gaps
        if include_gaps and feature_type:
            common_gaps = self.get_common_gaps_for_feature(feature_type)
            if common_gaps:
                context_parts.append(f"\n### Common Missing Scenarios for {feature_type.title()} Features\n")
                context_parts.append("Based on historical data, these scenarios are often missed:\n")
                for gap in common_gaps:
                    context_parts.append(f"- {gap}")
                context_parts.append("")

        if not context_parts:
            return ""

        # Add usage guidance
        header = "## Similar Test Cases from Past Projects\n\n"
        footer = "\n**How to use this context:**\n"
        footer += "- Use these as reference patterns and inspiration\n"
        footer += "- Adapt patterns to fit the current PRD requirements\n"
        footer += "- Ensure coverage of commonly missed scenarios\n"
        footer += "- Don't copy verbatim - generate tests specific to current feature\n"

        return header + "\n".join(context_parts) + footer

    # ========================================================================
    # Post-Generation Gap Analysis (Strategy A)
    # ========================================================================

    def analyze_coverage_gaps(
        self,
        generated_tests: List[TestCase],
        feature_name: str,
        prd_content: str = "",
    ) -> Dict[str, Any]:
        """
        Analyze coverage gaps by comparing generated tests with historical patterns.

        This is called AFTER test generation to identify potentially missing scenarios
        based on what similar features have tested historically.

        Args:
            generated_tests: List of newly generated test cases
            feature_name: Name of the feature being tested
            prd_content: Optional PRD content for better similarity matching

        Returns:
            Dictionary with:
            - missing_scenarios: List of potentially missing test scenarios
            - coverage_insights: Analysis of coverage compared to history
            - suggested_tests: Suggested additional test descriptions
            - confidence: Confidence score of the analysis
        """
        if not self.enabled:
            return {
                "missing_scenarios": [],
                "coverage_insights": "RAG not available for gap analysis",
                "suggested_tests": [],
                "confidence": 0,
            }

        try:
            # Build query from feature name and PRD
            query = f"{feature_name} {prd_content[:500] if prd_content else ''}"

            # Get similar historical tests
            similar_tests = self.get_similar_tests(query=query, top_k=20)

            if not similar_tests:
                return {
                    "missing_scenarios": [],
                    "coverage_insights": "No similar historical tests found - this may be a new feature type",
                    "suggested_tests": [],
                    "confidence": 0,
                }

            # Extract test types and features from generated tests
            generated_types = set(tc.test_type for tc in generated_tests)
            set(tc.feature.lower() for tc in generated_tests)
            generated_descriptions = set(
                tc.requirement_description.lower()[:100] for tc in generated_tests
            )

            # Analyze what's in history but not in generated
            missing_scenarios = []
            suggested_tests = []
            historical_types = Counter()
            historical_patterns = []

            for hist_test in similar_tests:
                metadata = hist_test.get("metadata", {})
                hist_type = metadata.get("test_type", "positive")
                hist_desc = metadata.get("requirement_description", "")[:100].lower()
                hist_priority = metadata.get("priority", "P2")

                historical_types[hist_type] += 1

                # Check if this pattern exists in generated tests
                is_covered = any(
                    self._similarity_check(hist_desc, gen_desc)
                    for gen_desc in generated_descriptions
                )

                if not is_covered and hist_desc:
                    # This is a potential gap
                    historical_patterns.append({
                        "description": metadata.get("requirement_description", ""),
                        "test_type": hist_type,
                        "priority": hist_priority,
                        "feature": metadata.get("feature", ""),
                        "score": hist_test.get("score", 0),
                    })

            # Identify missing test types
            common_types = {"positive", "negative", "edge_case", "boundary"}
            missing_types = common_types - generated_types

            # Build missing scenarios list
            if missing_types:
                for mtype in missing_types:
                    if historical_types.get(mtype, 0) > 2:  # Common in history
                        missing_scenarios.append(
                            f"No {mtype} tests generated - historically {historical_types[mtype]} "
                            f"such tests exist for similar features"
                        )

            # Get top suggested tests (unique patterns from history)
            seen_patterns = set()
            for pattern in sorted(historical_patterns, key=lambda x: x["score"], reverse=True):
                pattern_key = pattern["description"][:50].lower()
                if pattern_key not in seen_patterns and len(suggested_tests) < 5:
                    seen_patterns.add(pattern_key)
                    suggested_tests.append({
                        "description": pattern["description"],
                        "test_type": pattern["test_type"],
                        "priority": pattern["priority"],
                        "source_feature": pattern["feature"],
                        "reason": "Similar features tested this scenario",
                    })

            # Add common gaps for detected feature type
            detected_type = self._detect_feature_type(
                generated_tests[0] if generated_tests else None
            ) or "general"
            common_gaps = self.get_common_gaps_for_feature(detected_type)

            for gap in common_gaps[:3]:
                if not any(gap.lower() in sd.get("description", "").lower()
                          for sd in suggested_tests):
                    missing_scenarios.append(f"Historical gap: {gap}")

            # Calculate confidence based on data quality
            confidence = min(100, len(similar_tests) * 5)  # More history = more confidence

            # Build coverage insights
            type_distribution = dict(historical_types)
            insights = []

            if generated_types:
                insights.append(f"Generated tests cover: {', '.join(sorted(generated_types))}")

            if missing_types:
                insights.append(f"Missing test types: {', '.join(sorted(missing_types))}")

            if len(similar_tests) > 10:
                insights.append(f"Based on {len(similar_tests)} similar historical tests")

            return {
                "missing_scenarios": missing_scenarios,
                "coverage_insights": " | ".join(insights) if insights else "Analysis complete",
                "suggested_tests": suggested_tests,
                "confidence": confidence,
                "historical_type_distribution": type_distribution,
                "feature_type_detected": detected_type,
            }

        except Exception as e:
            logger.error(f"Gap analysis failed: {e}")
            return {
                "missing_scenarios": [],
                "coverage_insights": f"Gap analysis error: {str(e)}",
                "suggested_tests": [],
                "confidence": 0,
            }

    def _similarity_check(self, text1: str, text2: str, threshold: float = 0.5) -> bool:
        """
        Simple word-overlap similarity check between two texts.

        Args:
            text1: First text
            text2: Second text
            threshold: Minimum overlap ratio to consider similar

        Returns:
            True if texts are similar enough
        """
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))

        if not words1 or not words2:
            return False

        overlap = len(words1 & words2)
        min_len = min(len(words1), len(words2))

        return (overlap / min_len) >= threshold if min_len > 0 else False

    # ========================================================================
    # Statistics & Health Methods
    # ========================================================================

    def get_rag_stats(self) -> Dict[str, Any]:
        """
        Get RAG system statistics.

        Returns:
            Dictionary with collection stats and health status
        """
        stats = {
            "enabled": self.enabled,
            "qdrant_host": self.qdrant_host,
            "qdrant_port": self.qdrant_port,
            "health": "healthy" if self.enabled else "degraded",
        }

        if not self.enabled:
            return stats

        try:
            # Get stats from each collection
            test_cases_stats = self.test_cases_rag.get_stats()
            prd_stats = self.prd_rag.get_stats()
            coverage_stats = self.coverage_rag.get_stats()
            zk_config_stats = self.zk_config_rag.get_stats()

            stats["test_cases"] = {
                "count": test_cases_stats.get("points_count", 0),
                "collection": "test_cases_v1",
            }

            stats["prd_documents"] = {
                "count": prd_stats.get("points_count", 0),
                "collection": "prd_documents_v1",
            }

            stats["coverage_insights"] = {
                "count": coverage_stats.get("points_count", 0),
                "collection": "coverage_insights_v1",
            }

            stats["zk_config_docs"] = {
                "count": zk_config_stats.get("points_count", 0),
                "collection": "zk_config_docs",
            }

            # Live ZK config stats
            zk_live_stats = self.zk_live_rag.get_stats()
            stats["zk_live_config"] = {
                "count": zk_live_stats.get("points_count", 0),
                "collection": "zk_live_config",
            }

            stats["total_documents"] = (
                stats["test_cases"]["count"] +
                stats["prd_documents"]["count"] +
                stats["coverage_insights"]["count"] +
                stats["zk_config_docs"]["count"] +
                stats["zk_live_config"]["count"]
            )

        except Exception as e:
            logger.error(f"Error getting RAG stats: {e}")
            stats["error"] = str(e)
            stats["health"] = "error"

        return stats

    # ========================================================================
    # Bugs Knowledge Methods
    # ========================================================================

    def get_bugs_context(
        self,
        query: str,
        feature_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant bugs from bugs_knowledge collection.

        This helps test generation by providing context about:
        - Known bugs in similar features
        - Common bug patterns to watch for
        - Historical issues that tests should cover

        Args:
            query: Search query (feature name, screen, etc.)
            feature_filter: Optional filter by feature name
            top_k: Number of results to return

        Returns:
            List of relevant bugs with metadata
        """
        if not self.enabled:
            return []

        try:
            # Create embedder for bugs collection
            bugs_store = QdrantStore(
                collection_name="bugs_knowledge",
                embedding_dim=self.test_cases_rag.embedder.dimension,
            )

            query_embedding = self.test_cases_rag.embedder.embed_single(query)

            # Build filter
            filter_dict = None
            if feature_filter:
                filter_dict = {"feature_name": feature_filter}

            # Search
            results = bugs_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_dict=filter_dict,
                score_threshold=0.15,  # Lower threshold to catch more relevant bugs
            )

            # Format results
            formatted = []
            for result in results:
                metadata = result.get("payload", result.get("metadata", {}))
                formatted.append({
                    "bug_id": metadata.get("bug_id", ""),
                    "title": metadata.get("title", ""),
                    "category": metadata.get("category", ""),
                    "priority": metadata.get("priority", ""),
                    "screen": metadata.get("screen", ""),
                    "feature_name": metadata.get("feature_name", ""),
                    "status": metadata.get("status", ""),
                    "dev_type": metadata.get("dev_type", ""),
                    "description": metadata.get("description", "")[:200],
                    "score": result.get("score", 0),
                })

            return formatted

        except Exception as e:
            logger.warning(f"Failed to get bugs context: {e}")
            return []

    def format_bugs_context(self, bugs: List[Dict[str, Any]]) -> str:
        """
        Format bugs as context for LLM test generation.

        Args:
            bugs: List of bugs from get_bugs_context()

        Returns:
            Formatted string for LLM prompt
        """
        if not bugs:
            return ""

        context_parts = ["## KNOWN BUGS (Reference for Test Coverage)\n"]
        context_parts.append("These bugs were found in similar features. Consider adding tests to prevent regression:\n")

        for bug in bugs[:3]:  # Max 3 bugs to keep context small
            priority = bug.get("priority", "")
            title = bug.get("title", "")[:100]
            screen = bug.get("screen", "")
            category = bug.get("category", "")
            status = bug.get("status", "")

            status_icon = "✅" if status == "Fixed" else "⚠️"
            context_parts.append(f"• **[{priority}]** {title}")
            context_parts.append(f"  Screen: {screen} | Category: {category} | Status: {status_icon} {status}")

        context_parts.append("\n**Test Coverage Hint**: Ensure tests cover scenarios that could trigger these bugs.\n")

        return "\n".join(context_parts)

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _detect_feature_type(self, test_case: Any) -> str:
        """
        Auto-detect feature type from test case content.

        Uses keyword matching on requirement description and test steps.

        Args:
            test_case: TestCase object or mock object with required fields

        Returns:
            Detected feature type (payment, auth, etc.) or "general"
        """
        # Support both old and new field names
        test_scenario = getattr(test_case, 'test_scenario', '') or getattr(test_case, 'requirement_description', '')
        steps = getattr(test_case, 'steps_to_execute', '') or getattr(test_case, 'test_step', '')

        # Combine searchable text
        text = f"{test_scenario} {steps}".lower()

        # Score each feature type
        scores = {}
        for feature_type, keywords in FEATURE_TYPE_PATTERNS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[feature_type] = score

        # Return highest scoring type
        if scores:
            return max(scores, key=scores.get)

        return "general"

    def _extract_user_states(self, test_case: TestCase) -> List[str]:
        """
        Extract user states mentioned in test case.

        Args:
            test_case: TestCase object

        Returns:
            List of detected user states
        """
        # Support both old and new field names
        test_scenario = getattr(test_case, 'test_scenario', '') or getattr(test_case, 'requirement_description', '')
        steps = getattr(test_case, 'steps_to_execute', '') or getattr(test_case, 'test_step', '')

        text = f"{test_scenario} {steps}".lower()

        states = []
        state_patterns = {
            "new": r"\bnew\s+user\b|\bfirst\s+time\b",
            "subscribed": r"\bsubscribed\b|\bpremium\b|\bpaid\b",
            "expired": r"\bexpired\b|\blapsed\b",
            "trial": r"\btrial\b|\bfree\s+trial\b",
            "logged_in": r"\blogged\s+in\b|\bauthenticated\b",
            "guest": r"\bguest\b|\bunauth",
        }

        for state, pattern in state_patterns.items():
            if re.search(pattern, text):
                states.append(state)

        return states

    def _extract_screens(self, test_case: TestCase) -> List[str]:
        """
        Extract screen names mentioned in test case.

        Args:
            test_case: TestCase object

        Returns:
            List of detected screen names
        """
        # Support both old and new field names
        text = getattr(test_case, 'steps_to_execute', '') or getattr(test_case, 'test_step', '')

        # Look for common screen name patterns
        # e.g., "ChatScreen", "Recharge screen", "Home page"
        screen_patterns = [
            r"([A-Z][a-z]+(?:Screen|Page|View))",  # CamelCase screens
            r"([A-Z][a-z]+\s+(?:screen|page|view))",  # Title case screens
        ]

        screens = set()
        for pattern in screen_patterns:
            matches = re.findall(pattern, text)
            screens.update(matches)

        # Also check if test case has screens attribute (for user_journey tests)
        if hasattr(test_case, 'screens') and test_case.screens:
            screens.update(test_case.screens)

        return list(screens)

    def _rank_test_results(
        self,
        results: List[Dict[str, Any]],
        query: str,
        feature_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rank test case results using multiple factors.

        Factors:
        - Semantic similarity (cosine score)
        - Recency (newer tests ranked higher)
        - Quality (coverage score)
        - Type match (matching feature type gets boost)

        Args:
            results: Raw search results
            query: Original query
            feature_type: Expected feature type

        Returns:
            Ranked results
        """
        now = datetime.now()

        for result in results:
            metadata = result.get("metadata", {})
            base_score = result.get("score", 0)

            # Recency boost (decay over 30 days)
            generated_at = metadata.get("generated_at")
            if generated_at:
                try:
                    gen_date = datetime.fromisoformat(generated_at)
                    days_old = (now - gen_date).days
                    recency_boost = 1.0 / (1 + days_old / 30)
                except Exception:
                    recency_boost = 0.5
            else:
                recency_boost = 0.5

            # Quality boost (coverage score)
            coverage = metadata.get("coverage_score", 50)
            quality_boost = coverage / 100

            # Type match boost
            type_boost = 1.2 if metadata.get("feature_type_detected") == feature_type else 1.0

            # Priority boost (P0 > P1 > P2 > P3)
            priority_map = {"P0": 1.3, "P1": 1.1, "P2": 1.0, "P3": 0.9}
            priority_boost = priority_map.get(metadata.get("priority", "P2"), 1.0)

            # Calculate final score
            final_score = (
                base_score *
                recency_boost *
                quality_boost *
                type_boost *
                priority_boost
            )

            result["final_score"] = final_score

        # Sort by final score
        return sorted(results, key=lambda x: x.get("final_score", 0), reverse=True)

    # ========================================================================
    # Feature/Version Management Methods (NEW)
    # ========================================================================

    def get_features_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all unique features with their versions.

        Returns:
            List of features with version info:
            [
                {
                    "feature_name": "Payment Processing",
                    "versions": [
                        {
                            "version": 1,
                            "session_id": "Payment_Processing_V1",
                            "documents_included": ["prd", "frontend_lld"],
                            "frontend_count": 45,
                            "backend_count": 38,
                            "last_updated": "2026-01-14T23:45:00"
                        }
                    ]
                }
            ]
        """
        if not self.enabled:
            return []

        try:
            # Get all test cases
            all_points = self.test_cases_rag.store.client.scroll(
                collection_name=self.test_cases_rag.store.collection_name,
                limit=10000,
                with_payload=True,
            )[0]

            # Group by feature name and version
            features_dict: Dict[str, Dict[int, Dict]] = {}

            for point in all_points:
                payload = point.payload or {}
                session_id = payload.get("session_id", "")

                # Extract feature name from session_id (format: FeatureName_V1)
                # Handle both old format (Feature Name (date)) and new format (Feature_Name_V1)
                feature_name = ""
                version = 1

                if "_V" in session_id:
                    # New format: Feature_Name_V1
                    parts = session_id.rsplit("_V", 1)
                    feature_name = parts[0].replace("_", " ")
                    try:
                        version = int(parts[1]) if len(parts) > 1 else 1
                    except ValueError:
                        version = 1
                elif " (" in session_id:
                    # Old format: Feature Name (date)
                    feature_name = session_id.split(" (")[0]
                    version = payload.get("version", 1)
                else:
                    feature_name = session_id
                    version = payload.get("version", 1)

                if not feature_name:
                    continue

                # Initialize feature if not exists
                if feature_name not in features_dict:
                    features_dict[feature_name] = {}

                # Initialize version if not exists
                if version not in features_dict[feature_name]:
                    features_dict[feature_name][version] = {
                        "version": version,
                        "session_id": session_id,
                        "documents_included": payload.get("documents_included", ["prd"]),
                        "frontend_count": 0,
                        "backend_count": 0,
                        "last_updated": payload.get("last_updated", payload.get("generated_at", "")),
                    }

                # Count tests by scope
                test_scope = payload.get("test_scope", "frontend")
                if test_scope == "backend":
                    features_dict[feature_name][version]["backend_count"] += 1
                else:
                    features_dict[feature_name][version]["frontend_count"] += 1

                # Update documents_included if current has more
                current_docs = payload.get("documents_included", [])
                if len(current_docs) > len(features_dict[feature_name][version]["documents_included"]):
                    features_dict[feature_name][version]["documents_included"] = current_docs

            # Convert to list format
            result = []
            for feature_name, versions in sorted(features_dict.items()):
                result.append({
                    "feature_name": feature_name,
                    "versions": sorted(versions.values(), key=lambda v: v["version"]),
                })

            return result

        except Exception as e:
            logger.error(f"Error getting features list: {e}", exc_info=True)
            return []

    def get_feature_versions(self, feature_name: str) -> List[Dict[str, Any]]:
        """
        Get all versions of a specific feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of versions with details
        """
        features = self.get_features_list()
        for feature in features:
            if feature["feature_name"].lower() == feature_name.lower():
                return feature["versions"]
        return []

    async def update_version_documents(
        self,
        session_id: str,
        new_documents: List[str],
    ) -> Dict[str, Any]:
        """
        Update the documents_included field for all test cases in a version.

        Args:
            session_id: Session ID (e.g., "Payment_Processing_V1")
            new_documents: Updated list of documents

        Returns:
            Update statistics
        """
        if not self.enabled:
            return {"status": "error", "reason": "RAG not enabled"}

        try:
            # Get all points with this session_id
            points = self.test_cases_rag.store.client.scroll(
                collection_name=self.test_cases_rag.store.collection_name,
                scroll_filter={
                    "must": [{"key": "session_id", "match": {"value": session_id}}]
                },
                limit=10000,
                with_payload=True,
            )[0]

            if not points:
                return {"status": "error", "reason": "No test cases found for session"}

            # Update each point's payload
            updated_count = 0
            for point in points:
                payload = point.payload or {}
                payload["documents_included"] = new_documents
                payload["last_updated"] = datetime.now().isoformat()

                self.test_cases_rag.store.client.set_payload(
                    collection_name=self.test_cases_rag.store.collection_name,
                    payload=payload,
                    points=[point.id],
                )
                updated_count += 1

            return {
                "status": "success",
                "updated_count": updated_count,
                "documents_included": new_documents,
            }

        except Exception as e:
            logger.error(f"Error updating version documents: {e}", exc_info=True)
            return {"status": "error", "reason": str(e)}

    def _chunk_text(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk
            chunk_size: Size of each chunk
            chunk_overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to find a good break point (newline or period)
            if end < len(text):
                # Look for newline
                newline_pos = text.rfind('\n', start, end)
                if newline_pos > start + chunk_size // 2:
                    end = newline_pos + 1
                else:
                    # Look for period
                    period_pos = text.rfind('. ', start, end)
                    if period_pos > start + chunk_size // 2:
                        end = period_pos + 2

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - chunk_overlap

        return chunks


# ============================================================================
# Factory Function
# ============================================================================

def get_test_case_rag(
    qdrant_host: Optional[str] = None,
    qdrant_port: Optional[int] = None,
) -> TestCaseRAG:
    """
    Factory function to get TestCaseRAG instance.

    Handles initialization and error cases gracefully.

    Args:
        qdrant_host: Optional Qdrant host
        qdrant_port: Optional Qdrant port

    Returns:
        TestCaseRAG instance
    """
    try:
        return TestCaseRAG(qdrant_host=qdrant_host, qdrant_port=qdrant_port)
    except Exception as e:
        logger.error(f"Failed to create TestCaseRAG: {e}")
        # Return disabled instance for graceful degradation
        rag = TestCaseRAG.__new__(TestCaseRAG)
        rag.enabled = False
        return rag
