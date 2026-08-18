"""
Embedding Provider

Supports multiple embedding backends:
- OpenAI (text-embedding-3-small) - Best quality, requires API key
- Local sentence-transformers - Free, runs locally

Usage:
    provider = EmbeddingProvider(provider="openai", api_key="sk-...")
    embeddings = provider.embed(["text 1", "text 2"])
"""

import logging
import os
from typing import List, Literal, Optional

import numpy as np

logger = logging.getLogger(__name__)

EmbeddingProviderType = Literal["openai", "local"]


class EmbeddingProvider:
    """Provides text embeddings from various sources."""
    
    # Embedding dimensions for each provider
    DIMENSIONS = {
        "openai": 1536,  # text-embedding-3-small
        "openai-large": 3072,  # text-embedding-3-large
        "local": 384,  # all-MiniLM-L6-v2
    }
    
    def __init__(
        self,
        provider: EmbeddingProviderType = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize embedding provider.
        
        Args:
            provider: "openai" or "local"
            api_key: API key for OpenAI (uses env var if not provided)
            model: Model name override
        """
        self.provider = provider
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if provider == "openai":
            self.model = model or "text-embedding-3-small"
            self.dimension = 1536
            self._init_openai()
        else:
            self.model = model or "all-MiniLM-L6-v2"
            self.dimension = 384
            self._init_local()
        
        logger.info(f"Initialized {provider} embedding provider with model: {self.model}")
    
    def _init_openai(self):
        """Initialize OpenAI client."""
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key."
            )
        
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package required. Run: pip install openai")
    
    def _init_local(self):
        """Initialize local sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
            self.model_instance = SentenceTransformer(self.model)
            logger.info(f"Loaded local model: {self.model}")
        except ImportError:
            raise ImportError(
                "sentence-transformers required for local embeddings. "
                "Run: pip install sentence-transformers"
            )
    
    def embed(self, texts: List[str], batch_size: int = 100) -> np.ndarray:
        """Generate embeddings for texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            
        Returns:
            numpy array of shape (len(texts), dimension)
        """
        if not texts:
            return np.array([])
        
        if self.provider == "openai":
            return self._embed_openai(texts, batch_size)
        else:
            return self._embed_local(texts, batch_size)
    
    def _embed_openai(self, texts: List[str], batch_size: int) -> np.ndarray:
        """Generate embeddings using OpenAI API."""
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Clean texts (OpenAI has issues with empty strings)
            batch = [t if t.strip() else " " for t in batch]
            
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"OpenAI embedding error: {e}")
                # Return zero vectors for failed batch
                all_embeddings.extend([[0.0] * self.dimension] * len(batch))
        
        return np.array(all_embeddings)
    
    def _embed_local(self, texts: List[str], batch_size: int) -> np.ndarray:
        """Generate embeddings using local model."""
        embeddings = self.model_instance.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 100,
            convert_to_numpy=True
        )
        return embeddings
    
    def embed_single(self, text: str) -> np.ndarray:
        """Embed a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            1D numpy array of embeddings
        """
        result = self.embed([text])
        return result[0] if len(result) > 0 else np.zeros(self.dimension)
