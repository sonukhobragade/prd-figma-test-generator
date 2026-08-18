"""
Simple RAG - Main Interface

A practical RAG system for test case generation.
Indexes your React Native codebase and retrieves relevant context.

Usage:
    rag = SimpleRAG()
    
    # Index codebase (only once, stored persistently)
    rag.index_codebase("/path/to/project")
    
    # Get context for test generation
    context = rag.get_context("recharge payment UPI")
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .embeddings import EmbeddingProvider
from .qdrant_store import QdrantStore

logger = logging.getLogger(__name__)


class SimpleRAG:
    """Simple RAG system for test intelligence."""
    
    # File extensions to index
    CODE_EXTENSIONS = {'.ts', '.tsx', '.js', '.jsx'}
    DOC_EXTENSIONS = {'.md', '.txt', '.json'}
    
    # Directories to skip
    SKIP_DIRS = {
        'node_modules', '.git', 'build', 'dist', 'coverage',
        '__tests__', '__mocks__', '.expo', 'android/build',
        'ios/build', 'ios/Pods', '.gradle', '.idea', '.vscode'
    }
    
    def __init__(
        self,
        collection_name: str = "app_code",  # Use the indexed codebase collection
        qdrant_host: str = "localhost",
        qdrant_port: int = 6335,  # Docker container maps 6335->6333
        embedding_provider: str = "local",  # Use local embeddings to match indexed data
        openai_api_key: Optional[str] = None,
    ):
        """Initialize SimpleRAG.

        Args:
            collection_name: Qdrant collection name (default: app_code with indexed RN codebase)
            qdrant_host: Qdrant host
            qdrant_port: Qdrant port
            embedding_provider: "openai" or "local" (default: local for 384d sentence-transformers)
            openai_api_key: OpenAI API key (uses env var if not provided)
        """
        self.collection_name = collection_name

        # Initialize embedding provider
        # Default to local (sentence-transformers) to match the indexed codebase
        self.embedder = EmbeddingProvider(
            provider=embedding_provider,
            api_key=openai_api_key,
        )
        
        # Initialize Qdrant store
        self.store = QdrantStore(
            collection_name=collection_name,
            host=qdrant_host,
            port=qdrant_port,
            dimension=self.embedder.dimension,
        )
        
        # Track indexed files (to avoid re-indexing)
        self._indexed_files: Set[str] = set()
        
        logger.info(f"SimpleRAG initialized with collection: {collection_name}")
    
    def index_codebase(
        self,
        project_path: str,
        force_reindex: bool = False,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> Dict[str, Any]:
        """Index a React Native codebase.
        
        Args:
            project_path: Path to project root
            force_reindex: If True, reindex everything
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            
        Returns:
            Indexing statistics
        """
        project_path = Path(project_path)
        if not project_path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")
        
        logger.info(f"Indexing codebase: {project_path}")
        
        # Check if already indexed
        if not force_reindex and not self.store.is_empty():
            stats = self.store.get_stats()
            logger.info(f"Collection already has {stats['points_count']} documents. "
                       f"Use force_reindex=True to reindex.")
            return {"status": "skipped", "existing_docs": stats['points_count']}
        
        # If force reindex, clear collection
        if force_reindex:
            logger.info("Force reindex requested, clearing collection...")
            self.store.delete_collection()
            self.store = QdrantStore(
                collection_name=self.collection_name,
                host=self.store.host,
                port=self.store.port,
                dimension=self.embedder.dimension,
            )
        
        # Find and process files
        all_chunks = []
        all_metadata = []
        stats = {
            "files_processed": 0,
            "chunks_created": 0,
            "screens_found": 0,
            "components_found": 0,
            "api_calls_found": 0,
        }
        
        # Process code files
        for file_path in self._find_files(project_path, self.CODE_EXTENSIONS):
            try:
                chunks, metadata = self._process_code_file(
                    file_path, project_path, chunk_size, chunk_overlap
                )
                all_chunks.extend(chunks)
                all_metadata.extend(metadata)
                stats["files_processed"] += 1
                
                # Count types
                for meta in metadata:
                    if meta.get("type") == "screen":
                        stats["screens_found"] += 1
                    elif meta.get("type") == "component":
                        stats["components_found"] += 1
                    if meta.get("has_api_call"):
                        stats["api_calls_found"] += 1
                        
            except Exception as e:
                logger.warning(f"Error processing {file_path}: {e}")
        
        # Process documentation files
        for file_path in self._find_files(project_path, self.DOC_EXTENSIONS):
            try:
                chunks, metadata = self._process_doc_file(
                    file_path, project_path, chunk_size, chunk_overlap
                )
                all_chunks.extend(chunks)
                all_metadata.extend(metadata)
            except Exception as e:
                logger.warning(f"Error processing {file_path}: {e}")
        
        stats["chunks_created"] = len(all_chunks)
        
        if not all_chunks:
            logger.warning("No chunks to index!")
            return {"status": "empty", **stats}
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(all_chunks)} chunks...")
        embeddings = self.embedder.embed(all_chunks)
        
        # Store in Qdrant
        logger.info("Storing in Qdrant...")
        self.store.add_documents(all_chunks, embeddings, all_metadata)
        
        stats["status"] = "success"
        logger.info(f"Indexing complete: {stats}")
        
        return stats
    
    def get_context(
        self,
        query: str,
        top_k: int = 10,
        filter_type: Optional[str] = None,
        include_metadata: bool = True,
    ) -> str:
        """Get relevant context for a query.
        
        Args:
            query: Search query (e.g., "recharge payment flow")
            top_k: Number of results to return
            filter_type: Filter by type (screen, component, api, etc.)
            include_metadata: Include file paths and types in context
            
        Returns:
            Formatted context string for LLM
        """
        # Generate query embedding
        query_embedding = self.embedder.embed_single(query)
        
        # Build filter
        filter_dict = None
        if filter_type:
            filter_dict = {"type": filter_type}
        
        # Search
        results = self.store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_dict=filter_dict,
            score_threshold=0.3,  # Minimum relevance
        )
        
        if not results:
            return ""
        
        # Format context
        context_parts = []
        context_parts.append("## Relevant Code Context\n")
        
        for i, result in enumerate(results, 1):
            meta = result.get("metadata", {})
            text = result.get("text", "")
            score = result.get("score", 0)
            
            if include_metadata:
                context_parts.append(f"### [{i}] {meta.get('file_path', 'Unknown')} (relevance: {score:.2f})")
                if meta.get("type"):
                    context_parts.append(f"**Type**: {meta['type']}")
                if meta.get("component_name"):
                    context_parts.append(f"**Component**: {meta['component_name']}")
            
            context_parts.append(f"```\n{text}\n```\n")
        
        return "\n".join(context_parts)
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search and return raw results.
        
        Args:
            query: Search query
            top_k: Number of results
            filter_type: Optional type filter
            
        Returns:
            List of search results
        """
        query_embedding = self.embedder.embed_single(query)
        
        filter_dict = {"type": filter_type} if filter_type else None
        
        return self.store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_dict=filter_dict,
        )
    
    def get_screens(self) -> List[Dict[str, Any]]:
        """Get all indexed screens."""
        # Use a generic query to get screens
        query_embedding = self.embedder.embed_single("screen component view")
        return self.store.search(
            query_embedding=query_embedding,
            top_k=100,
            filter_dict={"type": "screen"},
        )
    
    def get_api_endpoints(self) -> List[Dict[str, Any]]:
        """Get all indexed API endpoints."""
        query_embedding = self.embedder.embed_single("api endpoint fetch axios")
        return self.store.search(
            query_embedding=query_embedding,
            top_k=100,
            filter_dict={"has_api_call": True},
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG statistics."""
        return self.store.get_stats()
    
    # ============ Private Methods ============
    
    def _find_files(self, base_path: Path, extensions: Set[str]) -> List[Path]:
        """Find files with given extensions."""
        files = []
        
        for root, dirs, filenames in os.walk(base_path):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            
            for filename in filenames:
                if Path(filename).suffix in extensions:
                    files.append(Path(root) / filename)
        
        return files
    
    def _process_code_file(
        self,
        file_path: Path,
        project_path: Path,
        chunk_size: int,
        chunk_overlap: int,
    ) -> tuple[List[str], List[Dict]]:
        """Process a code file into chunks."""
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return [], []
        
        relative_path = str(file_path.relative_to(project_path))
        
        # Detect file type
        file_type = self._detect_file_type(content, relative_path)
        component_name = self._extract_component_name(content)
        has_api = self._has_api_call(content)
        
        # Extract key information
        extracted_info = self._extract_code_info(content)
        
        # Create chunks
        chunks = self._chunk_text(content, chunk_size, chunk_overlap)
        
        # Create metadata for each chunk
        metadata = []
        for i, chunk in enumerate(chunks):
            meta = {
                "file_path": relative_path,
                "type": file_type,
                "component_name": component_name,
                "has_api_call": has_api,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "indexed_at": datetime.now().isoformat(),
            }
            
            # Add extracted info to first chunk
            if i == 0 and extracted_info:
                meta["extracted_info"] = json.dumps(extracted_info)
            
            metadata.append(meta)
        
        return chunks, metadata
    
    def _process_doc_file(
        self,
        file_path: Path,
        project_path: Path,
        chunk_size: int,
        chunk_overlap: int,
    ) -> tuple[List[str], List[Dict]]:
        """Process a documentation file into chunks."""
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return [], []
        
        relative_path = str(file_path.relative_to(project_path))
        
        # Create chunks
        chunks = self._chunk_text(content, chunk_size, chunk_overlap)
        
        # Create metadata
        metadata = []
        for i, chunk in enumerate(chunks):
            metadata.append({
                "file_path": relative_path,
                "type": "documentation",
                "chunk_index": i,
                "total_chunks": len(chunks),
                "indexed_at": datetime.now().isoformat(),
            })
        
        return chunks, metadata
    
    def _detect_file_type(self, content: str, file_path: str) -> str:
        """Detect the type of code file."""
        path_lower = file_path.lower()
        
        # Check path-based indicators
        if '/screen' in path_lower or 'screen.' in path_lower:
            return "screen"
        if '/component' in path_lower:
            return "component"
        if '/api/' in path_lower or '/service' in path_lower:
            return "api"
        if '/hook' in path_lower:
            return "hook"
        if '/store' in path_lower or '/redux' in path_lower:
            return "store"
        if '/util' in path_lower or '/helper' in path_lower:
            return "utility"
        if '/constant' in path_lower or '/config' in path_lower:
            return "config"
        if '/type' in path_lower or '.d.ts' in path_lower:
            return "types"
        
        # Check content-based indicators
        if re.search(r'Screen|Page|View', content) and 'export' in content:
            return "screen"
        if re.search(r'const\s+\w+\s*=\s*\([^)]*\)\s*=>', content):
            return "component"
        if re.search(r'fetch|axios|api\.', content):
            return "api"
        
        return "code"
    
    def _extract_component_name(self, content: str) -> Optional[str]:
        """Extract component/screen name from content."""
        patterns = [
            r'export\s+(?:default\s+)?(?:function|const)\s+([A-Z][a-zA-Z0-9]*)',
            r'const\s+([A-Z][a-zA-Z0-9]*)\s*(?::\s*React\.FC)?.*=',
            r'class\s+([A-Z][a-zA-Z0-9]*)\s+extends',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
        
        return None
    
    def _has_api_call(self, content: str) -> bool:
        """Check if file contains API calls."""
        api_patterns = [
            r'fetch\s*\(',
            r'axios\.',
            r'api\.',
            r'apiClient\.',
            r'\.get\s*\(',
            r'\.post\s*\(',
            r'\.put\s*\(',
            r'\.delete\s*\(',
        ]
        
        for pattern in api_patterns:
            if re.search(pattern, content):
                return True
        return False
    
    def _extract_code_info(self, content: str) -> Dict[str, Any]:
        """Extract key information from code."""
        info = {}
        
        # Extract imports
        imports = re.findall(r"import\s+.*?from\s+['\"]([^'\"]+)['\"]", content)
        if imports:
            info["imports"] = imports[:20]  # Limit
        
        # Extract navigation targets
        nav_targets = re.findall(
            r"navigation\.(?:navigate|push)\s*\(\s*['\"]([^'\"]+)['\"]",
            content
        )
        if nav_targets:
            info["navigation_targets"] = list(set(nav_targets))
        
        # Extract API endpoints
        endpoints = re.findall(
            r"['\"`](/api/[^'\"`]+)['\"`]",
            content
        )
        if endpoints:
            info["api_endpoints"] = list(set(endpoints))
        
        return info
    
    def _chunk_text(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to find a good break point
            if end < len(text):
                # Look for newline
                newline_pos = text.rfind('\n', start, end)
                if newline_pos > start + chunk_size // 2:
                    end = newline_pos + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - chunk_overlap
        
        return chunks
