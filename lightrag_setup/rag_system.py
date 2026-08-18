#!/usr/bin/env python3
"""
LightRAG Test Intelligence System
==================================

Simple, persistent RAG system for test case generation.
Uses LightRAG for knowledge graph + vector retrieval.

Usage:
    # 1. Start Qdrant
    docker-compose up -d
    
    # 2. Ingest your codebase
    python rag_system.py ingest
    
    # 3. Query for test cases
    python rag_system.py query "What test cases are needed for RechargeScreen?"
"""

import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

# Load environment
load_dotenv()


@dataclass
class DocumentChunk:
    """A chunk of document for ingestion."""
    content: str
    source: str
    doc_type: str  # 'code', 'prd', 'figma', 'knowledge'
    metadata: Dict[str, Any] = None


class TestIntelligenceRAG:
    """
    RAG system for test case generation using LightRAG.
    
    Features:
    - Persistent vector storage with Qdrant
    - Knowledge graph for relationship understanding
    - Code-aware chunking
    - Test-focused querying
    """
    
    def __init__(self, working_dir: str = "./lightrag_data"):
        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)
        
        # Check for LightRAG
        try:
            from lightrag import LightRAG, QueryParam
            from lightrag.llm import openai_complete_if_cache, openai_embedding  # noqa: F401  (import is the availability check)
            self.LightRAG = LightRAG
            self.QueryParam = QueryParam
            self._has_lightrag = True
        except ImportError:
            console.print("[yellow]LightRAG not installed. Using fallback mode.[/yellow]")
            self._has_lightrag = False
        
        # Initialize Qdrant client
        try:
            from qdrant_client import QdrantClient
            
            self.qdrant = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", 6335))
            )
            self.collection_name = os.getenv("QDRANT_COLLECTION", "test_intelligence")
            self._has_qdrant = True
            console.print("[green]✓ Connected to Qdrant[/green]")
        except Exception as e:
            console.print(f"[yellow]Qdrant not available: {e}[/yellow]")
            self._has_qdrant = False
        
        # Initialize LightRAG if available
        if self._has_lightrag:
            self._init_lightrag()
        
        # Load or create document index
        self.index_file = self.working_dir / "document_index.json"
        self.document_index = self._load_index()
    
    def _init_lightrag(self):
        """Initialize LightRAG with appropriate settings."""
        try:
            # Use Anthropic for LLM
            async def anthropic_complete(prompt, **kwargs):
                import anthropic
                client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                response = client.messages.create(
                    model=os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            
            # Use OpenAI for embeddings (or local if not available)
            if os.getenv("OPENAI_API_KEY"):
                async def get_embedding(texts):
                    import openai
                    client = openai.OpenAI()
                    response = client.embeddings.create(
                        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
                        input=texts if isinstance(texts, list) else [texts]
                    )
                    return [e.embedding for e in response.data]
                
                embedding_func = get_embedding
                embedding_dim = 1536
            else:
                # Use local sentence-transformers
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer('all-MiniLM-L6-v2')
                
                async def local_embedding(texts):
                    if isinstance(texts, str):
                        texts = [texts]
                    return model.encode(texts).tolist()
                
                embedding_func = local_embedding
                embedding_dim = 384
            
            self.rag = self.LightRAG(
                working_dir=str(self.working_dir),
                llm_model_func=anthropic_complete,
                embedding_func=embedding_func,
                embedding_dim=embedding_dim,
            )
            console.print("[green]✓ LightRAG initialized[/green]")
            
        except Exception as e:
            console.print(f"[red]LightRAG init failed: {e}[/red]")
            self._has_lightrag = False
    
    def _load_index(self) -> Dict:
        """Load document index from disk."""
        if self.index_file.exists():
            return json.loads(self.index_file.read_text())
        return {"documents": [], "last_updated": None}
    
    def _save_index(self):
        """Save document index to disk."""
        self.document_index["last_updated"] = datetime.now().isoformat()
        self.index_file.write_text(json.dumps(self.document_index, indent=2))
    
    def ingest_codebase(self, codebase_path: str):
        """
        Ingest React Native codebase into RAG.
        
        Args:
            codebase_path: Path to React Native project
        """
        codebase = Path(codebase_path)
        if not codebase.exists():
            raise ValueError(f"Codebase not found: {codebase_path}")
        
        console.print(Panel(f"[bold]Ingesting Codebase[/bold]\n{codebase_path}"))
        
        chunks = []
        
        # File extensions to process
        extensions = {'.ts', '.tsx', '.js', '.jsx', '.json'}
        skip_dirs = {'node_modules', '.git', 'build', 'dist', '.expo', 'android/build', 'ios/Pods'}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Scanning files...", total=None)
            
            file_count = 0
            for root, dirs, files in os.walk(codebase):
                # Skip unwanted directories
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                
                for file in files:
                    if Path(file).suffix not in extensions:
                        continue
                    
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(codebase)
                    
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        
                        # Create chunks based on file type
                        file_chunks = self._chunk_code_file(content, str(relative_path))
                        chunks.extend(file_chunks)
                        file_count += 1
                        
                        progress.update(task, description=f"Processing: {relative_path}")
                        
                    except Exception:
                        pass  # Skip unreadable files
            
            progress.update(task, description=f"Processed {file_count} files, {len(chunks)} chunks")
        
        # Ingest chunks
        self._ingest_chunks(chunks)
        
        console.print(f"[green]✓ Ingested {len(chunks)} chunks from {file_count} files[/green]")
    
    def _chunk_code_file(self, content: str, file_path: str) -> List[DocumentChunk]:
        """Chunk a code file intelligently."""
        chunks = []
        
        # Determine file type
        if file_path.endswith(('.tsx', '.jsx')):
            doc_type = 'component'
        elif 'api' in file_path.lower() or 'service' in file_path.lower():
            doc_type = 'api'
        elif 'screen' in file_path.lower():
            doc_type = 'screen'
        elif 'constants' in file_path.lower() or 'config' in file_path.lower():
            doc_type = 'config'
        else:
            doc_type = 'code'
        
        # Simple chunking: split by function/component definitions
        # For now, use fixed-size chunks with overlap
        chunk_size = 1500
        overlap = 200
        
        if len(content) <= chunk_size:
            chunks.append(DocumentChunk(
                content=f"File: {file_path}\n\n{content}",
                source=file_path,
                doc_type=doc_type,
                metadata={"file_path": file_path, "type": doc_type}
            ))
        else:
            # Split into overlapping chunks
            for i in range(0, len(content), chunk_size - overlap):
                chunk_content = content[i:i + chunk_size]
                chunks.append(DocumentChunk(
                    content=f"File: {file_path} (chunk {i // (chunk_size - overlap) + 1})\n\n{chunk_content}",
                    source=file_path,
                    doc_type=doc_type,
                    metadata={"file_path": file_path, "type": doc_type, "chunk_index": i}
                ))
        
        return chunks
    
    def _ingest_chunks(self, chunks: List[DocumentChunk]):
        """Ingest chunks into RAG system."""
        
        # Store in Qdrant if available
        if self._has_qdrant:
            self._store_in_qdrant(chunks)
        
        # Store in LightRAG if available
        if self._has_lightrag:
            self._store_in_lightrag(chunks)
        
        # Update index
        for chunk in chunks:
            self.document_index["documents"].append({
                "source": chunk.source,
                "doc_type": chunk.doc_type,
                "ingested_at": datetime.now().isoformat()
            })
        
        self._save_index()
    
    def _store_in_qdrant(self, chunks: List[DocumentChunk]):
        """Store chunks in Qdrant."""
        from qdrant_client.models import Distance, VectorParams, PointStruct
        
        # Ensure collection exists
        try:
            self.qdrant.get_collection(self.collection_name)
        except Exception:
            # Create collection
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
        
        # Get embeddings
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            texts = [c.content for c in chunks]
            embeddings = model.encode(texts)
            
            # Upload to Qdrant
            points = [
                PointStruct(
                    id=i,
                    vector=embeddings[i].tolist(),
                    payload={
                        "content": chunks[i].content[:1000],  # Truncate for storage
                        "source": chunks[i].source,
                        "doc_type": chunks[i].doc_type
                    }
                )
                for i in range(len(chunks))
            ]
            
            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            console.print(f"[green]✓ Stored {len(points)} vectors in Qdrant[/green]")
            
        except Exception as e:
            console.print(f"[yellow]Qdrant storage failed: {e}[/yellow]")
    
    def _store_in_lightrag(self, chunks: List[DocumentChunk]):
        """Store chunks in LightRAG."""
        try:
            # LightRAG expects plain text
            combined_text = "\n\n---\n\n".join([c.content for c in chunks])
            
            # Run async insertion
            asyncio.run(self.rag.ainsert(combined_text))
            
            console.print("[green]✓ Stored in LightRAG knowledge graph[/green]")
            
        except Exception as e:
            console.print(f"[yellow]LightRAG storage failed: {e}[/yellow]")
    
    def ingest_prd(self, prd_path: str):
        """Ingest a PRD document."""
        prd_file = Path(prd_path)
        if not prd_file.exists():
            raise ValueError(f"PRD not found: {prd_path}")
        
        content = ""
        
        if prd_path.endswith('.pdf'):
            try:
                from pypdf import PdfReader
                reader = PdfReader(prd_path)
                content = "\n".join([page.extract_text() for page in reader.pages])
            except Exception as e:
                console.print(f"[red]Failed to read PDF: {e}[/red]")
                return
        elif prd_path.endswith('.md'):
            content = prd_file.read_text()
        elif prd_path.endswith('.docx'):
            try:
                from docx import Document
                doc = Document(prd_path)
                content = "\n".join([p.text for p in doc.paragraphs])
            except Exception as e:
                console.print(f"[red]Failed to read DOCX: {e}[/red]")
                return
        else:
            content = prd_file.read_text()
        
        chunks = [DocumentChunk(
            content=f"PRD Document: {prd_file.name}\n\n{content}",
            source=str(prd_path),
            doc_type='prd',
            metadata={"file_path": str(prd_path)}
        )]
        
        self._ingest_chunks(chunks)
        console.print(f"[green]✓ Ingested PRD: {prd_file.name}[/green]")
    
    def ingest_knowledge_base(self, kb_path: str):
        """Ingest existing knowledge base files."""
        kb_dir = Path(kb_path)
        if not kb_dir.exists():
            raise ValueError(f"Knowledge base not found: {kb_path}")
        
        chunks = []
        
        for file in kb_dir.glob("*.md"):
            content = file.read_text()
            chunks.append(DocumentChunk(
                content=f"Knowledge Base: {file.name}\n\n{content}",
                source=str(file),
                doc_type='knowledge',
                metadata={"file_path": str(file), "kb_type": file.stem}
            ))
        
        self._ingest_chunks(chunks)
        console.print(f"[green]✓ Ingested {len(chunks)} knowledge base files[/green]")
    
    def query(self, question: str, mode: str = "hybrid") -> str:
        """
        Query the RAG system.
        
        Args:
            question: Query string
            mode: Query mode - 'naive', 'local', 'global', 'hybrid'
            
        Returns:
            Response from RAG system
        """
        console.print(Panel(f"[bold]Query[/bold]\n{question}"))
        
        results = []
        
        # Query Qdrant for relevant chunks
        if self._has_qdrant:
            qdrant_results = self._query_qdrant(question)
            if qdrant_results:
                results.extend(qdrant_results)
        
        # Query LightRAG if available
        if self._has_lightrag:
            try:
                response = asyncio.run(
                    self.rag.aquery(question, param=self.QueryParam(mode=mode))
                )
                return response
            except Exception as e:
                console.print(f"[yellow]LightRAG query failed: {e}[/yellow]")
        
        # Fallback: use retrieved context with Claude
        if results:
            return self._generate_response(question, results)
        
        return "No relevant information found. Please ingest documents first."
    
    def _query_qdrant(self, question: str, top_k: int = 5) -> List[str]:
        """Query Qdrant for relevant chunks."""
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            query_vector = model.encode(question).tolist()
            
            results = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k
            )
            
            return [r.payload.get("content", "") for r in results]
            
        except Exception as e:
            console.print(f"[yellow]Qdrant query failed: {e}[/yellow]")
            return []
    
    def _generate_response(self, question: str, context: List[str]) -> str:
        """Generate response using Claude with retrieved context."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            
            context_text = "\n\n---\n\n".join(context)
            
            prompt = f"""Based on the following code and documentation context, answer the question.

CONTEXT:
{context_text}

QUESTION: {question}

Provide a detailed, helpful answer based on the context. If generating test cases, be specific and actionable."""
            
            response = client.messages.create(
                model=os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            return f"Error generating response: {e}"
    
    def generate_test_cases(self, feature: str) -> str:
        """Generate test cases for a specific feature."""
        query = f"""Generate comprehensive test cases for the {feature} feature.

Include:
1. Positive test cases (happy paths)
2. Negative test cases (error handling)
3. Boundary value tests
4. Edge cases
5. User state variations (new user, subscribed, expired)

Format each test case with:
- Description
- Preconditions
- Steps
- Expected Result
- Priority (P0/P1/P2/P3)
- Test Type"""
        
        return self.query(query)
    
    def get_status(self) -> Dict:
        """Get system status."""
        status = {
            "lightrag_available": self._has_lightrag,
            "qdrant_available": self._has_qdrant,
            "documents_ingested": len(self.document_index.get("documents", [])),
            "last_updated": self.document_index.get("last_updated"),
            "working_dir": str(self.working_dir)
        }
        
        if self._has_qdrant:
            try:
                info = self.qdrant.get_collection(self.collection_name)
                status["qdrant_vectors"] = info.points_count
            except Exception:
                status["qdrant_vectors"] = 0
        
        return status


def main():
    """CLI interface."""
    import typer
    app = typer.Typer(help="LightRAG Test Intelligence System")
    
    @app.command()
    def status():
        """Show system status."""
        rag = TestIntelligenceRAG()
        status = rag.get_status()
        
        table = Table(title="System Status")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        
        table.add_row("LightRAG", "✓ Available" if status["lightrag_available"] else "✗ Not installed")
        table.add_row("Qdrant", "✓ Connected" if status["qdrant_available"] else "✗ Not running")
        table.add_row("Documents Ingested", str(status["documents_ingested"]))
        table.add_row("Qdrant Vectors", str(status.get("qdrant_vectors", 0)))
        table.add_row("Last Updated", status["last_updated"] or "Never")
        
        console.print(table)
    
    @app.command()
    def ingest(
        path: str = typer.Argument(..., help="Path to codebase, PRD, or knowledge base"),
        doc_type: str = typer.Option("auto", help="Document type: auto, code, prd, knowledge")
    ):
        """Ingest documents into RAG."""
        rag = TestIntelligenceRAG()
        
        path_obj = Path(path)
        
        if doc_type == "auto":
            if path_obj.is_dir():
                if (path_obj / "package.json").exists():
                    doc_type = "code"
                elif any(path_obj.glob("*.md")):
                    doc_type = "knowledge"
                else:
                    doc_type = "code"
            elif path_obj.suffix in ['.pdf', '.docx', '.md']:
                doc_type = "prd"
            else:
                doc_type = "code"
        
        if doc_type == "code":
            rag.ingest_codebase(path)
        elif doc_type == "prd":
            rag.ingest_prd(path)
        elif doc_type == "knowledge":
            rag.ingest_knowledge_base(path)
    
    @app.command()
    def query(
        question: str = typer.Argument(..., help="Question to ask"),
        mode: str = typer.Option("hybrid", help="Query mode: naive, local, global, hybrid")
    ):
        """Query the RAG system."""
        rag = TestIntelligenceRAG()
        response = rag.query(question, mode)
        console.print(Panel(response, title="Response"))
    
    @app.command()
    def testcases(
        feature: str = typer.Argument(..., help="Feature to generate test cases for")
    ):
        """Generate test cases for a feature."""
        rag = TestIntelligenceRAG()
        response = rag.generate_test_cases(feature)
        console.print(Panel(response, title=f"Test Cases: {feature}"))
    
    app()


if __name__ == "__main__":
    main()
