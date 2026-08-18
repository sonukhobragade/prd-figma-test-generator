"""
RAG-Enhanced Knowledge Base

Extends the existing knowledge base to include RAG-retrieved context
from the indexed codebase.

This module automatically:
1. Gets relevant code context from Qdrant
2. Combines with static knowledge base files
3. Provides enriched context to the LLM

Usage:
    # In llm_analyzer.py, replace:
    #   from framework.knowledge_base import get_knowledge_base
    # With:
    #   from rag.enhanced_kb import get_enhanced_knowledge_base
"""

import logging
from typing import Optional

from framework.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


class EnhancedKnowledgeBase(KnowledgeBase):
    """Knowledge base enhanced with RAG retrieval."""
    
    def __init__(self, kb_dir=None, enable_rag: bool = True):
        """Initialize enhanced knowledge base.
        
        Args:
            kb_dir: Path to knowledge base directory
            enable_rag: Whether to enable RAG retrieval
        """
        super().__init__(kb_dir)
        
        self.rag = None
        self.rag_enabled = enable_rag
        
        if enable_rag:
            self._init_rag()
    
    def _init_rag(self):
        """Initialize RAG connection (lazy loading)."""
        try:
            from rag import SimpleRAG

            # Check if Qdrant is available
            import requests
            import os
            qdrant_port = os.getenv("QDRANT_PORT", "6335")
            try:
                response = requests.get(f"http://localhost:{qdrant_port}/", timeout=2)
                if response.status_code == 200:
                    # Use local embeddings and the indexed codebase collection
                    self.rag = SimpleRAG(
                        collection_name="app_code",  # The indexed React Native codebase
                        embedding_provider="local",  # Use sentence-transformers (384d)
                    )
                    stats = self.rag.get_stats()
                    if stats.get('points_count', 0) > 0:
                        logger.info(f"RAG enabled with {stats['points_count']} indexed documents from React Native codebase")
                    else:
                        logger.warning("RAG collection is empty. Run: cd lightrag_setup && python simple_rag.py ingest /path/to/codebase")
                        self.rag = None
            except requests.exceptions.RequestException:
                logger.info("Qdrant not running. RAG features disabled.")
                self.rag = None

        except ImportError as e:
            logger.warning(f"RAG dependencies not installed: {e}")
            self.rag = None
    
    def get_rag_context(
        self,
        query: str,
        top_k: int = 5,
        filter_type: Optional[str] = None,
    ) -> str:
        """Get relevant context from RAG.
        
        Args:
            query: Search query
            top_k: Number of results
            filter_type: Optional type filter (screen, component, api)
            
        Returns:
            Formatted context string
        """
        if not self.rag:
            return ""
        
        try:
            return self.rag.get_context(query, top_k=top_k, filter_type=filter_type)
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            return ""
    
    def get_summary_context(self) -> str:
        """Override to add RAG stats to summary.
        
        Returns:
            Enhanced summary context string
        """
        # Get base summary
        base_summary = super().get_summary_context()
        
        # Add RAG status
        if self.rag:
            try:
                stats = self.rag.get_stats()
                rag_info = f"""
## Codebase Context (RAG)
Indexed documents: {stats.get('points_count', 0)}
Collection: {stats.get('name', 'unknown')}

The system has access to your indexed codebase for:
- Screen names and navigation flows
- API endpoints and methods
- Component structures
- Validation rules from code
"""
                return base_summary + rag_info
            except Exception:
                pass
        
        return base_summary
    
    def get_enhanced_context(
        self,
        prd_content: str = "",
        feature_name: str = "",
        max_static_chars: int = 30000,
        max_rag_results: int = 8,
    ) -> str:
        """Get enhanced context combining static KB and RAG.
        
        Args:
            prd_content: PRD content to extract query from
            feature_name: Feature name for query
            max_static_chars: Max chars for static KB content
            max_rag_results: Max RAG results to include
            
        Returns:
            Combined context string
        """
        parts = []
        
        # 1. Static knowledge base summary
        static_context = self.get_summary_context()
        if static_context:
            parts.append(static_context)
        
        # 2. RAG context (if available)
        if self.rag:
            # Build query from feature name and PRD content
            query_parts = []
            if feature_name:
                query_parts.append(feature_name)
            
            # Extract key terms from PRD
            if prd_content:
                # Look for key features/screens mentioned
                import re
                screens = re.findall(r'([A-Z][a-z]+(?:Screen|Page|View|Modal))', prd_content)
                query_parts.extend(screens[:3])
                
                # Look for key actions
                actions = re.findall(r'(recharge|payment|subscription|chat|report|login|signup)', 
                                    prd_content.lower())
                query_parts.extend(list(set(actions))[:3])
            
            if query_parts:
                query = " ".join(query_parts)
                rag_context = self.get_rag_context(query, top_k=max_rag_results)
                if rag_context:
                    parts.append("\n" + rag_context)
        
        return "\n".join(parts)
    
    def get_screen_context(self, screen_name: str) -> str:
        """Get context for a specific screen.
        
        Args:
            screen_name: Name of the screen
            
        Returns:
            Context about the screen
        """
        if not self.rag:
            return ""
        
        return self.get_rag_context(screen_name, top_k=5, filter_type="screen")
    
    def get_api_context(self, endpoint_hint: str) -> str:
        """Get context about API endpoints.
        
        Args:
            endpoint_hint: Hint about the endpoint (e.g., "payment", "user")
            
        Returns:
            Context about relevant APIs
        """
        if not self.rag:
            return ""
        
        return self.get_rag_context(f"api {endpoint_hint}", top_k=5)


# Global instance
_enhanced_kb: Optional[EnhancedKnowledgeBase] = None


def get_enhanced_knowledge_base() -> EnhancedKnowledgeBase:
    """Get or create the enhanced knowledge base instance."""
    global _enhanced_kb
    if _enhanced_kb is None:
        _enhanced_kb = EnhancedKnowledgeBase()
    return _enhanced_kb
