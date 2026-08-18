#!/usr/bin/env python3
"""
Feature Manager - Manages features and their linked documents (PRD, Figma, Codebase).

Features act as the central grouping mechanism that links:
- PRD documents
- Figma designs
- Codebase context (auto-linked via keywords)
- Generated test cases

All documents are stored in Qdrant (port 6335) with feature_id as the linking key.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Qdrant settings - using lightrag-qdrant on port 6335
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_LIGHTRAG_PORT", "6335"))
EMBEDDING_DIM = 1536  # OpenAI embeddings


@dataclass
class Feature:
    """A feature that groups related documents."""
    id: str
    name: str
    keywords: List[str]
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    prd_count: int = 0
    figma_count: int = 0
    test_count: int = 0
    codebase_files: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FeatureDocument:
    """A document linked to a feature."""
    id: str
    feature_id: str
    doc_type: str  # 'prd', 'figma', 'codebase'
    name: str
    content: str = ""
    metadata: Dict = None
    created_at: str = ""

    def to_dict(self) -> Dict:
        d = asdict(self)
        if d['metadata'] is None:
            d['metadata'] = {}
        return d


class FeatureManager:
    """
    Manages features and their linked documents.

    Uses Qdrant for persistent storage with collections:
    - app_features: Feature metadata
    - feature_documents: PRD/Figma documents linked to features
    """

    FEATURES_COLLECTION = "app_features"
    DOCUMENTS_COLLECTION = "feature_documents"

    def __init__(self, qdrant_host: str = None, qdrant_port: int = None):
        self.host = qdrant_host or QDRANT_HOST
        self.port = qdrant_port or QDRANT_PORT
        self.client = None
        self.embedder = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of Qdrant client and embeddings."""
        if self._initialized:
            return True

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self.client = QdrantClient(host=self.host, port=self.port, timeout=5)

            # Verify connection
            self.client.get_collections()

            # Create collections if they don't exist
            existing = [c.name for c in self.client.get_collections().collections]

            if self.FEATURES_COLLECTION not in existing:
                # Features collection - stores feature metadata (no vectors needed)
                self.client.create_collection(
                    collection_name=self.FEATURES_COLLECTION,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIM,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.FEATURES_COLLECTION}")

            if self.DOCUMENTS_COLLECTION not in existing:
                # Documents collection - stores PRD/Figma content with vectors
                self.client.create_collection(
                    collection_name=self.DOCUMENTS_COLLECTION,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIM,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.DOCUMENTS_COLLECTION}")

            self._initialized = True
            logger.info(f"FeatureManager connected to Qdrant at {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize FeatureManager: {e}")
            self._initialized = False
            return False

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using OpenAI."""
        if self.embedder is None:
            try:
                import openai
                self.embedder = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI embedder: {e}")
                # Return zero vector as fallback
                return [0.0] * EMBEDDING_DIM

        try:
            response = self.embedder.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000]  # Limit input length
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return [0.0] * EMBEDDING_DIM

    def _generate_id(self, prefix: str = "feat") -> str:
        """Generate a unique ID."""
        return f"{prefix}_{uuid4().hex[:8]}"

    def _slug_id(self, name: str) -> str:
        """Generate a slug-based ID from name."""
        slug = name.lower().replace(" ", "_").replace("-", "_")
        # Remove special characters
        slug = "".join(c for c in slug if c.isalnum() or c == "_")
        return f"feat_{slug}"

    # ─────────────────────────────────────────────────────────────────
    # FEATURE CRUD
    # ─────────────────────────────────────────────────────────────────

    def create_feature(
        self,
        name: str,
        keywords: List[str],
        description: str = ""
    ) -> Optional[Feature]:
        """
        Create a new feature.

        Args:
            name: Display name for the feature
            keywords: Keywords for auto-linking codebase
            description: Optional description

        Returns:
            Created Feature object or None if failed
        """
        if not self._ensure_initialized():
            return None

        try:
            from qdrant_client.models import PointStruct

            # Generate slug-based ID for consistency
            feature_id = self._slug_id(name)
            now = datetime.now().isoformat()

            feature = Feature(
                id=feature_id,
                name=name,
                keywords=keywords,
                description=description,
                created_at=now,
                updated_at=now,
            )

            # Create embedding from name + keywords + description
            embed_text = f"{name} {' '.join(keywords)} {description}"
            embedding = self._get_embedding(embed_text)

            # Store in Qdrant
            self.client.upsert(
                collection_name=self.FEATURES_COLLECTION,
                points=[
                    PointStruct(
                        id=hash(feature_id) % (2**63),
                        vector=embedding,
                        payload=feature.to_dict()
                    )
                ]
            )

            logger.info(f"Created feature: {feature_id} ({name})")
            return feature

        except Exception as e:
            logger.error(f"Failed to create feature: {e}")
            return None

    def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Get a feature by ID."""
        if not self._ensure_initialized():
            return None

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            results = self.client.scroll(
                collection_name=self.FEATURES_COLLECTION,
                scroll_filter=Filter(
                    must=[FieldCondition(key="id", match=MatchValue(value=feature_id))]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )

            points, _ = results
            if points:
                payload = points[0].payload
                return Feature(**payload)
            return None

        except Exception as e:
            logger.error(f"Failed to get feature {feature_id}: {e}")
            return None

    def list_features(self) -> List[Feature]:
        """List all features."""
        if not self._ensure_initialized():
            return []

        try:
            all_points = []
            offset = None

            while True:
                results = self.client.scroll(
                    collection_name=self.FEATURES_COLLECTION,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                points, offset = results
                all_points.extend(points)

                if offset is None:
                    break

            features = []
            for point in all_points:
                try:
                    features.append(Feature(**point.payload))
                except Exception as e:
                    logger.warning(f"Failed to parse feature: {e}")

            # Sort by name
            features.sort(key=lambda f: f.name.lower())
            return features

        except Exception as e:
            logger.error(f"Failed to list features: {e}")
            return []

    def update_feature(
        self,
        feature_id: str,
        name: str = None,
        keywords: List[str] = None,
        description: str = None
    ) -> Optional[Feature]:
        """Update a feature."""
        if not self._ensure_initialized():
            return None

        feature = self.get_feature(feature_id)
        if not feature:
            return None

        try:
            from qdrant_client.models import PointStruct

            # Update fields
            if name is not None:
                feature.name = name
            if keywords is not None:
                feature.keywords = keywords
            if description is not None:
                feature.description = description
            feature.updated_at = datetime.now().isoformat()

            # Update embedding
            embed_text = f"{feature.name} {' '.join(feature.keywords)} {feature.description}"
            embedding = self._get_embedding(embed_text)

            # Upsert (update)
            self.client.upsert(
                collection_name=self.FEATURES_COLLECTION,
                points=[
                    PointStruct(
                        id=hash(feature_id) % (2**63),
                        vector=embedding,
                        payload=feature.to_dict()
                    )
                ]
            )

            logger.info(f"Updated feature: {feature_id}")
            return feature

        except Exception as e:
            logger.error(f"Failed to update feature: {e}")
            return None

    def delete_feature(self, feature_id: str) -> bool:
        """Delete a feature and all its linked documents."""
        if not self._ensure_initialized():
            return False

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Delete feature
            self.client.delete(
                collection_name=self.FEATURES_COLLECTION,
                points_selector=Filter(
                    must=[FieldCondition(key="id", match=MatchValue(value=feature_id))]
                )
            )

            # Delete linked documents
            self.client.delete(
                collection_name=self.DOCUMENTS_COLLECTION,
                points_selector=Filter(
                    must=[FieldCondition(key="feature_id", match=MatchValue(value=feature_id))]
                )
            )

            logger.info(f"Deleted feature and documents: {feature_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete feature: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────
    # DOCUMENT MANAGEMENT
    # ─────────────────────────────────────────────────────────────────

    def add_document(
        self,
        feature_id: str,
        doc_type: str,
        name: str,
        content: str,
        metadata: Dict = None
    ) -> Optional[FeatureDocument]:
        """
        Add a document (PRD/Figma) to a feature.

        Args:
            feature_id: ID of the feature to link to
            doc_type: Type of document ('prd', 'figma', 'codebase')
            name: Document name/title
            content: Document content/text
            metadata: Additional metadata (figma_url, file_path, etc.)

        Returns:
            Created FeatureDocument or None
        """
        if not self._ensure_initialized():
            return None

        # Verify feature exists
        feature = self.get_feature(feature_id)
        if not feature:
            logger.error(f"Feature not found: {feature_id}")
            return None

        try:
            from qdrant_client.models import PointStruct

            doc_id = f"{feature_id}_{doc_type}_{uuid4().hex[:8]}"
            now = datetime.now().isoformat()

            doc = FeatureDocument(
                id=doc_id,
                feature_id=feature_id,
                doc_type=doc_type,
                name=name,
                content=content[:50000],  # Limit content size
                metadata=metadata or {},
                created_at=now,
            )

            # Create embedding from content
            embed_text = f"{name} {content[:5000]}"
            embedding = self._get_embedding(embed_text)

            # Store in Qdrant
            self.client.upsert(
                collection_name=self.DOCUMENTS_COLLECTION,
                points=[
                    PointStruct(
                        id=hash(doc_id) % (2**63),
                        vector=embedding,
                        payload=doc.to_dict()
                    )
                ]
            )

            # Update feature counts
            self._update_feature_counts(feature_id)

            logger.info(f"Added {doc_type} document to feature {feature_id}: {name}")
            return doc

        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            return None

    def get_feature_documents(
        self,
        feature_id: str,
        doc_type: str = None
    ) -> List[FeatureDocument]:
        """Get all documents linked to a feature."""
        if not self._ensure_initialized():
            return []

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            conditions = [
                FieldCondition(key="feature_id", match=MatchValue(value=feature_id))
            ]
            if doc_type:
                conditions.append(
                    FieldCondition(key="doc_type", match=MatchValue(value=doc_type))
                )

            all_points = []
            offset = None

            while True:
                results = self.client.scroll(
                    collection_name=self.DOCUMENTS_COLLECTION,
                    scroll_filter=Filter(must=conditions),
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                points, offset = results
                all_points.extend(points)

                if offset is None:
                    break

            docs = []
            for point in all_points:
                try:
                    docs.append(FeatureDocument(**point.payload))
                except Exception as e:
                    logger.warning(f"Failed to parse document: {e}")

            return docs

        except Exception as e:
            logger.error(f"Failed to get feature documents: {e}")
            return []

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document."""
        if not self._ensure_initialized():
            return False

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Get document to find feature_id
            results = self.client.scroll(
                collection_name=self.DOCUMENTS_COLLECTION,
                scroll_filter=Filter(
                    must=[FieldCondition(key="id", match=MatchValue(value=doc_id))]
                ),
                limit=1,
                with_payload=True,
            )
            points, _ = results
            feature_id = points[0].payload.get("feature_id") if points else None

            # Delete document
            self.client.delete(
                collection_name=self.DOCUMENTS_COLLECTION,
                points_selector=Filter(
                    must=[FieldCondition(key="id", match=MatchValue(value=doc_id))]
                )
            )

            # Update feature counts
            if feature_id:
                self._update_feature_counts(feature_id)

            logger.info(f"Deleted document: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    def _update_feature_counts(self, feature_id: str):
        """Update document counts for a feature."""
        try:

            # Count documents by type
            docs = self.get_feature_documents(feature_id)
            prd_count = sum(1 for d in docs if d.doc_type == 'prd')
            figma_count = sum(1 for d in docs if d.doc_type == 'figma')

            # Get feature and update
            feature = self.get_feature(feature_id)
            if feature:
                feature.prd_count = prd_count
                feature.figma_count = figma_count
                feature.updated_at = datetime.now().isoformat()

                # Update in Qdrant (re-use existing embedding)
                from qdrant_client.models import PointStruct
                embed_text = f"{feature.name} {' '.join(feature.keywords)}"
                embedding = self._get_embedding(embed_text)

                self.client.upsert(
                    collection_name=self.FEATURES_COLLECTION,
                    points=[
                        PointStruct(
                            id=hash(feature_id) % (2**63),
                            vector=embedding,
                            payload=feature.to_dict()
                        )
                    ]
                )

        except Exception as e:
            logger.warning(f"Failed to update feature counts: {e}")

    # ─────────────────────────────────────────────────────────────────
    # CONTEXT RETRIEVAL (for test generation)
    # ─────────────────────────────────────────────────────────────────

    def get_feature_context(self, feature_id: str) -> Dict[str, Any]:
        """
        Get all context for a feature (PRDs + Figma + Codebase).
        Used when generating test cases.

        Args:
            feature_id: Feature ID

        Returns:
            Dict with prd_content, figma_data, codebase_context
        """
        if not self._ensure_initialized():
            return {"prd_content": [], "figma_data": [], "codebase_context": []}

        docs = self.get_feature_documents(feature_id)

        prd_content = []
        figma_data = []
        codebase_context = []

        for doc in docs:
            if doc.doc_type == 'prd':
                prd_content.append({
                    "name": doc.name,
                    "content": doc.content,
                    "metadata": doc.metadata,
                })
            elif doc.doc_type == 'figma':
                figma_data.append({
                    "name": doc.name,
                    "content": doc.content,
                    "url": doc.metadata.get("figma_url", ""),
                    "metadata": doc.metadata,
                })
            elif doc.doc_type == 'codebase':
                codebase_context.append({
                    "name": doc.name,
                    "content": doc.content,
                    "file_path": doc.metadata.get("file_path", ""),
                })

        # Also try to get codebase context from keywords
        feature = self.get_feature(feature_id)
        if feature and feature.keywords:
            # Query codebase RAG with keywords
            try:
                from rag import SimpleRAG
                codebase_rag = SimpleRAG(
                    collection_name="app_code",
                    embedding_provider="local",
                )

                for keyword in feature.keywords[:3]:  # Limit queries
                    results = codebase_rag.search(keyword, top_k=3)
                    for r in results:
                        codebase_context.append({
                            "name": r.get("file_path", ""),
                            "content": r.get("content", "")[:2000],
                            "file_path": r.get("file_path", ""),
                            "matched_keyword": keyword,
                        })
            except Exception as e:
                logger.warning(f"Failed to get codebase context: {e}")

        return {
            "prd_content": prd_content,
            "figma_data": figma_data,
            "codebase_context": codebase_context,
        }

    def search_features(self, query: str, top_k: int = 5) -> List[Feature]:
        """Search features by semantic similarity."""
        if not self._ensure_initialized():
            return []

        try:
            embedding = self._get_embedding(query)

            results = self.client.search(
                collection_name=self.FEATURES_COLLECTION,
                query_vector=embedding,
                limit=top_k,
            )

            features = []
            for r in results:
                try:
                    features.append(Feature(**r.payload))
                except Exception:
                    pass

            return features

        except Exception as e:
            logger.error(f"Failed to search features: {e}")
            return []

    def get_status(self) -> Dict:
        """Get Feature Manager status."""
        if not self._ensure_initialized():
            return {
                "enabled": False,
                "health": "offline",
                "message": f"Cannot connect to Qdrant at {self.host}:{self.port}",
            }

        try:
            features = self.list_features()

            # Count documents
            all_docs = []
            offset = None
            while True:
                results = self.client.scroll(
                    collection_name=self.DOCUMENTS_COLLECTION,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                points, offset = results
                all_docs.extend(points)
                if offset is None:
                    break

            prd_count = sum(1 for d in all_docs if d.payload.get("doc_type") == "prd")
            figma_count = sum(1 for d in all_docs if d.payload.get("doc_type") == "figma")

            return {
                "enabled": True,
                "health": "healthy",
                "feature_count": len(features),
                "prd_count": prd_count,
                "figma_count": figma_count,
                "total_documents": len(all_docs),
                "qdrant_host": self.host,
                "qdrant_port": self.port,
            }

        except Exception as e:
            return {
                "enabled": False,
                "health": "error",
                "message": str(e),
            }


# Singleton instance
_feature_manager: Optional[FeatureManager] = None


def get_feature_manager() -> FeatureManager:
    """Get or create the singleton FeatureManager instance."""
    global _feature_manager
    if _feature_manager is None:
        _feature_manager = FeatureManager()
    return _feature_manager
