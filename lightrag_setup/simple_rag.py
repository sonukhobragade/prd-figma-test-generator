#!/usr/bin/env python3
"""
Simple Qdrant-based RAG for Test Case Generation
=================================================

This is a simpler, more reliable version that uses:
- Qdrant for vector storage (persistent!)
- sentence-transformers for embeddings (local, free)
- Claude for generation (your Claude Max)

No complex LightRAG dependency - just works!

Usage:
    # 1. Start Qdrant: docker-compose up -d
    # 2. Ingest: python simple_rag.py ingest
    # 3. Query: python simple_rag.py query "RechargeScreen test cases"
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

from dotenv import load_dotenv

load_dotenv()


@dataclass 
class CodeChunk:
    """A chunk of code with metadata."""
    id: str
    content: str
    file_path: str
    file_type: str  # screen, component, api, config, etc.
    embedding: List[float] = None
    
    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if k != 'embedding'}


class SimpleRAG:
    """
    Simple RAG system with Qdrant.
    
    - Persistent: Data survives restarts
    - Local embeddings: No OpenAI needed
    - Simple: Easy to understand and modify
    """
    
    COLLECTION_NAME = "app_code"
    EMBEDDING_DIM = 384  # all-MiniLM-L6-v2
    
    def __init__(self):
        # Initialize embedding model
        print("📦 Loading embedding model...")
        from sentence_transformers import SentenceTransformer
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Embedding model loaded")
        
        # Connect to Qdrant
        print("🔌 Connecting to Qdrant...")
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        
        self.qdrant = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", 6335))
        )
        
        # Create collection if not exists
        try:
            self.qdrant.get_collection(self.COLLECTION_NAME)
            print(f"✅ Connected to collection: {self.COLLECTION_NAME}")
        except Exception:
            self.qdrant.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.EMBEDDING_DIM,
                    distance=Distance.COSINE
                )
            )
            print(f"✅ Created collection: {self.COLLECTION_NAME}")
        
        # Data directory for metadata
        self.data_dir = Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)
    
    def _get_file_type(self, file_path: str) -> str:
        """Determine file type from path."""
        path_lower = file_path.lower()
        
        if 'screen' in path_lower or '/app/' in path_lower:
            return 'screen'
        elif 'api' in path_lower or 'service' in path_lower:
            return 'api'
        elif 'component' in path_lower:
            return 'component'
        elif 'hook' in path_lower:
            return 'hook'
        elif 'store' in path_lower or 'context' in path_lower:
            return 'state'
        elif 'constant' in path_lower or 'config' in path_lower:
            return 'config'
        elif 'util' in path_lower or 'helper' in path_lower:
            return 'utility'
        elif 'type' in path_lower:
            return 'types'
        else:
            return 'code'
    
    def _chunk_file(self, content: str, file_path: str, chunk_size: int = 1500) -> List[CodeChunk]:
        """Split file into chunks."""
        chunks = []
        file_type = self._get_file_type(file_path)
        
        # Add file header to each chunk for context
        header = f"// File: {file_path}\n// Type: {file_type}\n\n"
        
        if len(content) <= chunk_size:
            chunk_id = hashlib.md5(f"{file_path}:0".encode()).hexdigest()
            chunks.append(CodeChunk(
                id=chunk_id,
                content=header + content,
                file_path=file_path,
                file_type=file_type
            ))
        else:
            # Split into overlapping chunks
            overlap = 200
            for i in range(0, len(content), chunk_size - overlap):
                chunk_content = content[i:i + chunk_size]
                chunk_id = hashlib.md5(f"{file_path}:{i}".encode()).hexdigest()
                chunks.append(CodeChunk(
                    id=chunk_id,
                    content=header + chunk_content,
                    file_path=file_path,
                    file_type=file_type
                ))
        
        return chunks
    
    def ingest_codebase(self, codebase_path: str):
        """Ingest entire React Native codebase."""
        from qdrant_client.models import PointStruct
        
        codebase = Path(codebase_path)
        if not codebase.exists():
            raise ValueError(f"Path not found: {codebase_path}")
        
        print(f"\n📂 Ingesting codebase: {codebase_path}")
        print("=" * 50)
        
        # File extensions to process
        extensions = {'.ts', '.tsx', '.js', '.jsx'}
        skip_dirs = {'node_modules', '.git', 'build', 'dist', '.expo', 
                     'android/build', 'ios/Pods', '__tests__', '.gradle'}
        
        all_chunks = []
        file_count = 0
        
        for root, dirs, files in os.walk(codebase):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for file in files:
                if Path(file).suffix not in extensions:
                    continue
                
                file_path = Path(root) / file
                relative_path = str(file_path.relative_to(codebase))
                
                try:
                    content = file_path.read_text(encoding='utf-8')
                    chunks = self._chunk_file(content, relative_path)
                    all_chunks.extend(chunks)
                    file_count += 1
                    
                    if file_count % 50 == 0:
                        print(f"   Processed {file_count} files...")
                        
                except Exception:
                    pass  # Skip unreadable files
        
        print(f"\n📊 Found {file_count} files, {len(all_chunks)} chunks")
        
        # Generate embeddings in batches
        print("🧠 Generating embeddings...")
        batch_size = 32
        points = []
        
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            texts = [c.content for c in batch]
            embeddings = self.embedder.encode(texts)
            
            for j, chunk in enumerate(batch):
                points.append(PointStruct(
                    id=hash(chunk.id) % (2**63),  # Convert to int
                    vector=embeddings[j].tolist(),
                    payload=chunk.to_dict()
                ))
            
            if (i + batch_size) % 200 == 0:
                print(f"   Embedded {min(i + batch_size, len(all_chunks))}/{len(all_chunks)} chunks...")
        
        # Upload to Qdrant
        print("📤 Uploading to Qdrant...")
        
        # Upload in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.qdrant.upsert(
                collection_name=self.COLLECTION_NAME,
                points=batch
            )
        
        # Save metadata
        metadata = {
            "codebase_path": codebase_path,
            "file_count": file_count,
            "chunk_count": len(all_chunks),
            "ingested_at": datetime.now().isoformat(),
            "file_types": {}
        }
        
        for chunk in all_chunks:
            ft = chunk.file_type
            metadata["file_types"][ft] = metadata["file_types"].get(ft, 0) + 1
        
        (self.data_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
        
        print("\n" + "=" * 50)
        print("✅ INGESTION COMPLETE!")
        print("=" * 50)
        print(f"   Files processed: {file_count}")
        print(f"   Chunks created:  {len(all_chunks)}")
        print(f"   Vectors stored:  {len(points)}")
        print("\nFile types breakdown:")
        for ft, count in sorted(metadata["file_types"].items(), key=lambda x: -x[1]):
            print(f"   {ft}: {count}")
    
    def search(self, query: str, top_k: int = 10, file_type: Optional[str] = None) -> List[Dict]:
        """Search for relevant code chunks."""
        # Generate query embedding
        query_vector = self.embedder.encode(query).tolist()
        
        # Build filter if file_type specified
        query_filter = None
        if file_type:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            query_filter = Filter(
                must=[FieldCondition(key="file_type", match=MatchValue(value=file_type))]
            )
        
        # Search
        results = self.qdrant.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k
        )
        
        return [
            {
                "content": r.payload.get("content", ""),
                "file_path": r.payload.get("file_path", ""),
                "file_type": r.payload.get("file_type", ""),
                "score": r.score
            }
            for r in results
        ]
    
    def query(self, question: str, top_k: int = 8) -> str:
        """Query with Claude using retrieved context."""
        import anthropic
        
        # Search for relevant chunks
        print(f"\n🔍 Searching for: {question}")
        results = self.search(question, top_k=top_k)
        
        if not results:
            return "No relevant code found. Please ingest your codebase first."
        
        print(f"📄 Found {len(results)} relevant chunks")
        
        # Build context
        context_parts = []
        for r in results:
            context_parts.append(f"--- {r['file_path']} ({r['file_type']}) ---\n{r['content']}")
        
        context = "\n\n".join(context_parts)
        
        # Generate with Claude
        print("🤖 Generating response with Claude...")
        
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        prompt = f"""You are a senior QA engineer analyzing a React Native codebase. Based on the following code context, answer the question.

CODE CONTEXT:
{context}

QUESTION: {question}

Provide a detailed, specific answer. If generating test cases:
- Be specific to the actual code shown
- Include exact component/screen names
- Reference actual props, states, and functions
- Include boundary values from the code
- Cover both happy path and error scenarios"""

        response = client.messages.create(
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    def generate_test_cases(self, feature: str) -> str:
        """Generate comprehensive test cases for a feature."""
        # First, find the feature's code
        results = self.search(feature, top_k=15)
        
        if not results:
            return f"Could not find code for feature: {feature}"
        
        # Build context with focus on the feature
        context_parts = []
        for r in results:
            context_parts.append(f"--- {r['file_path']} ---\n{r['content']}")
        
        context = "\n\n".join(context_parts)
        
        # Generate test cases
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        prompt = f"""You are a senior QA engineer. Generate comprehensive test cases for the "{feature}" feature based on the following code.

CODE CONTEXT:
{context}

Generate test cases in this format:

## Test Cases for {feature}

### P0 - Critical Tests
| ID | Description | Preconditions | Steps | Expected Result |
|----|-------------|---------------|-------|-----------------|

### P1 - High Priority Tests  
| ID | Description | Preconditions | Steps | Expected Result |
|----|-------------|---------------|-------|-----------------|

### P2 - Medium Priority Tests
| ID | Description | Preconditions | Steps | Expected Result |
|----|-------------|---------------|-------|-----------------|

### Boundary Value Tests
(Based on actual min/max values in the code)

### Error Handling Tests
(Based on actual error handling in the code)

### User State Matrix
Test with: New User, Subscribed User, Expired User, Guest User

Be SPECIFIC - use actual component names, prop names, and values from the code!"""

        response = client.messages.create(
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    def get_stats(self) -> Dict:
        """Get system statistics."""
        try:
            collection = self.qdrant.get_collection(self.COLLECTION_NAME)
            
            # Load metadata
            metadata_file = self.data_dir / "metadata.json"
            metadata = {}
            if metadata_file.exists():
                metadata = json.loads(metadata_file.read_text())
            
            return {
                "status": "connected",
                "vectors_count": collection.points_count,
                "codebase_path": metadata.get("codebase_path", "Not ingested"),
                "file_count": metadata.get("file_count", 0),
                "chunk_count": metadata.get("chunk_count", 0),
                "ingested_at": metadata.get("ingested_at", "Never"),
                "file_types": metadata.get("file_types", {})
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


def main():
    """CLI interface."""
    import sys
    
    if len(sys.argv) < 2:
        print("""
Simple RAG for Test Case Generation
====================================

Usage:
    python simple_rag.py status              - Show system status
    python simple_rag.py ingest <path>       - Ingest codebase
    python simple_rag.py search <query>      - Search code
    python simple_rag.py query <question>    - Query with Claude
    python simple_rag.py testcases <feature> - Generate test cases

Examples:
    python simple_rag.py ingest /path/to/react-native-app
    python simple_rag.py query "How does RechargeScreen handle UPI payments?"
    python simple_rag.py testcases "Subscription Flow"
""")
        return
    
    command = sys.argv[1]
    
    if command == "status":
        rag = SimpleRAG()
        stats = rag.get_stats()
        print("\n📊 RAG System Status")
        print("=" * 40)
        for key, value in stats.items():
            if key == "file_types" and isinstance(value, dict):
                print("File Types:")
                for ft, count in value.items():
                    print(f"  - {ft}: {count}")
            else:
                print(f"{key}: {value}")
    
    elif command == "ingest":
        if len(sys.argv) < 3:
            print("Usage: python simple_rag.py ingest <path>")
            return
        path = sys.argv[2]
        rag = SimpleRAG()
        rag.ingest_codebase(path)
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python simple_rag.py search <query>")
            return
        query = " ".join(sys.argv[2:])
        rag = SimpleRAG()
        results = rag.search(query)
        print(f"\n🔍 Search Results for: {query}")
        print("=" * 50)
        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['file_path']} ({r['file_type']}) - Score: {r['score']:.3f}")
            print(f"   {r['content'][:200]}...")
    
    elif command == "query":
        if len(sys.argv) < 3:
            print("Usage: python simple_rag.py query <question>")
            return
        question = " ".join(sys.argv[2:])
        rag = SimpleRAG()
        response = rag.query(question)
        print("\n" + "=" * 50)
        print("RESPONSE:")
        print("=" * 50)
        print(response)
    
    elif command == "testcases":
        if len(sys.argv) < 3:
            print("Usage: python simple_rag.py testcases <feature>")
            return
        feature = " ".join(sys.argv[2:])
        rag = SimpleRAG()
        response = rag.generate_test_cases(feature)
        print(response)
        
        # Also save to file
        output_file = Path(__file__).parent / "output" / f"testcases_{feature.replace(' ', '_')}.md"
        output_file.parent.mkdir(exist_ok=True)
        output_file.write_text(response)
        print(f"\n✅ Saved to: {output_file}")
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
