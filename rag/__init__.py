"""
Simple RAG (Retrieval Augmented Generation) Module

A lightweight RAG system using Qdrant for persistent storage.
Designed to be simple and practical for test case generation.

Usage:
    from rag import SimpleRAG
    
    # Initialize
    rag = SimpleRAG()
    
    # Index your codebase (only needs to be done once)
    rag.index_codebase("/path/to/react-native-project")
    
    # Query for relevant context
    context = rag.get_context("recharge payment flow")
    
    # Use context in test generation
    test_cases = generate_tests(prd_content, context)
"""

from .simple_rag import SimpleRAG
from .qdrant_store import QdrantStore
from .embeddings import EmbeddingProvider
from .enhanced_kb import EnhancedKnowledgeBase, get_enhanced_knowledge_base

__all__ = [
    "SimpleRAG", 
    "QdrantStore", 
    "EmbeddingProvider",
    "EnhancedKnowledgeBase",
    "get_enhanced_knowledge_base",
]
