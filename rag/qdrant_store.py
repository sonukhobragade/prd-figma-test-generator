"""
Qdrant Vector Store

Simple wrapper around Qdrant for storing and retrieving embeddings.

Usage:
    store = QdrantStore()
    store.add_documents(texts, embeddings, metadata)
    results = store.search("query text", top_k=5)
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class QdrantStore:
    """Vector store using Qdrant."""
    
    def __init__(
        self,
        collection_name: str = "test_intelligence",
        host: str = "localhost",
        port: int = 6335,  # Docker container maps 6335->6333
        dimension: int = 1536,
    ):
        """Initialize Qdrant store.
        
        Args:
            collection_name: Name of the collection
            host: Qdrant host
            port: Qdrant port
            dimension: Embedding dimension
        """
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self.dimension = dimension
        
        self._init_client()
    
    def _init_client(self):
        """Initialize Qdrant client."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            
            self.client = QdrantClient(host=self.host, port=self.port)
            
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                # Create collection
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.dimension,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.collection_name}")
            else:
                logger.info(f"Using existing collection: {self.collection_name}")
                
        except ImportError:
            raise ImportError(
                "qdrant-client required. Run: pip install qdrant-client"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            logger.error("Make sure Qdrant is running: docker-compose up -d")
            raise
    
    def add_documents(
        self,
        texts: List[str],
        embeddings: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Add documents to the store.
        
        Args:
            texts: List of text content
            embeddings: Numpy array of embeddings
            metadata: Optional metadata for each document
            ids: Optional IDs (generated if not provided)
            
        Returns:
            List of document IDs
        """
        from qdrant_client.models import PointStruct
        
        if len(texts) != len(embeddings):
            raise ValueError("texts and embeddings must have same length")
        
        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
        
        # Prepare metadata
        if metadata is None:
            metadata = [{} for _ in texts]
        
        # Create points with unique string IDs
        # Qdrant supports both integer and string (UUID) IDs
        points = []
        for i, (text, embedding, meta, doc_id) in enumerate(zip(texts, embeddings, metadata, ids)):
            payload = {
                "text": text,
                **meta
            }
            points.append(PointStruct(
                id=doc_id,  # Use UUID string directly - ensures unique IDs across uploads
                vector=embedding.tolist(),
                payload=payload
            ))
        
        # Upsert to Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        logger.info(f"Added {len(points)} documents to {self.collection_name}")
        return ids
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search for similar documents.

        Args:
            query_embedding: Query vector
            top_k: Number of results
            filter_dict: Optional filter conditions
            score_threshold: Minimum similarity score

        Returns:
            List of results with text, metadata, and score
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # Build filter if provided
        qdrant_filter = None
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            qdrant_filter = Filter(must=conditions)

        # Search using query_points (new Qdrant API)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding.tolist(),
            limit=top_k,
            query_filter=qdrant_filter,
            score_threshold=score_threshold,
        )

        # Format results
        formatted = []
        for result in results.points:
            # Support both "text" (new format) and "content" (lightrag_setup format)
            text = result.payload.get("text", "") or result.payload.get("content", "")
            # Exclude both text and content from metadata
            metadata = {k: v for k, v in result.payload.items() if k not in ("text", "content")}
            formatted.append({
                "text": text,
                "metadata": metadata,
                "score": result.score,
                "id": result.id,
            })

        return formatted
    
    def delete_collection(self):
        """Delete the entire collection."""
        self.client.delete_collection(self.collection_name)
        logger.info(f"Deleted collection: {self.collection_name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        info = self.client.get_collection(self.collection_name)
        # Handle different Qdrant API versions
        points_count = getattr(info, 'points_count', 0)
        if points_count == 0:
            # Try alternative attribute names
            points_count = getattr(info, 'vectors_count', 0)

        return {
            "name": self.collection_name,
            "points_count": points_count,
            "status": getattr(info, 'status', 'unknown'),
        }
    
    def is_empty(self) -> bool:
        """Check if collection is empty."""
        stats = self.get_stats()
        return stats.get("points_count", 0) == 0
