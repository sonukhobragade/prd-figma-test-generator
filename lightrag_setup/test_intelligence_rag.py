#!/usr/bin/env python3
"""
Test Intelligence RAG System
=======================================

Integrated RAG system with:
- Qdrant for persistent vector storage
- Improved prompts matching QA team format
- CSV export for test case spreadsheets

Usage:
    # 1. Start Qdrant: docker-compose up -d
    # 2. Ingest: python test_intelligence_rag.py ingest
    # 3. Generate: python test_intelligence_rag.py generate "Recharge Flow"
"""

import os
import sys
import json
import csv
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

try:
    from framework.prompts.test_case_prompt import (
        TEST_CASE_PROMPT,
        SYSTEM_CONTEXT,
    )
    PROMPT_AVAILABLE = True
except ImportError:
    PROMPT_AVAILABLE = False


@dataclass 
class CodeChunk:
    id: str
    content: str
    file_path: str
    file_type: str
    
    def to_dict(self):
        return asdict(self)


class TestIntelligenceRAG:
    COLLECTION_NAME = "app_code"
    EMBEDDING_DIM = 384
    
    def __init__(self):
        print("🚀 Initializing Test Intelligence RAG...")
        from sentence_transformers import SentenceTransformer
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        
        self.qdrant = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", 6335))
        )
        
        try:
            self.qdrant.get_collection(self.COLLECTION_NAME)
            print(f"✅ Connected to Qdrant collection: {self.COLLECTION_NAME}")
        except Exception:
            self.qdrant.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=self.EMBEDDING_DIM, distance=Distance.COSINE)
            )
            print(f"✅ Created Qdrant collection: {self.COLLECTION_NAME}")
        
        self.data_dir = Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.output_dir = Path(__file__).parent / "output"
        self.output_dir.mkdir(exist_ok=True)
    
    def _get_file_type(self, file_path: str) -> str:
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
        else:
            return 'code'
    
    def _chunk_file(self, content: str, file_path: str, chunk_size: int = 1500) -> List[CodeChunk]:
        chunks = []
        file_type = self._get_file_type(file_path)
        header = f"// File: {file_path}\n// Type: {file_type}\n\n"
        
        if len(content) <= chunk_size:
            chunks.append(CodeChunk(
                id=hashlib.md5(f"{file_path}:0".encode()).hexdigest(),
                content=header + content,
                file_path=file_path,
                file_type=file_type
            ))
        else:
            overlap = 200
            for i in range(0, len(content), chunk_size - overlap):
                chunks.append(CodeChunk(
                    id=hashlib.md5(f"{file_path}:{i}".encode()).hexdigest(),
                    content=header + content[i:i + chunk_size],
                    file_path=file_path,
                    file_type=file_type
                ))
        return chunks
    
    def ingest_codebase(self, codebase_path: str):
        from qdrant_client.models import PointStruct
        codebase = Path(codebase_path)
        
        print(f"\n📂 INGESTING: {codebase_path}")
        
        extensions = {'.ts', '.tsx', '.js', '.jsx'}
        skip_dirs = {'node_modules', '.git', 'build', 'dist', '.expo', 'android/build', 'ios/Pods'}
        
        all_chunks = []
        file_count = 0
        
        for root, dirs, files in os.walk(codebase):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for file in files:
                if Path(file).suffix not in extensions:
                    continue
                try:
                    file_path = Path(root) / file
                    content = file_path.read_text(encoding='utf-8')
                    chunks = self._chunk_file(content, str(file_path.relative_to(codebase)))
                    all_chunks.extend(chunks)
                    file_count += 1
                    if file_count % 50 == 0:
                        print(f"   Processed {file_count} files...")
                except Exception:
                    pass
        
        print(f"📊 Found {file_count} files, {len(all_chunks)} chunks")
        print("🧠 Generating embeddings...")
        
        points = []
        for i in range(0, len(all_chunks), 32):
            batch = all_chunks[i:i + 32]
            embeddings = self.embedder.encode([c.content for c in batch])
            for j, chunk in enumerate(batch):
                points.append(PointStruct(
                    id=hash(chunk.id) % (2**63),
                    vector=embeddings[j].tolist(),
                    payload=chunk.to_dict()
                ))
        
        print("📤 Uploading to Qdrant...")
        for i in range(0, len(points), 100):
            self.qdrant.upsert(collection_name=self.COLLECTION_NAME, points=points[i:i+100])
        
        metadata = {"codebase_path": codebase_path, "file_count": file_count, 
                    "chunk_count": len(all_chunks), "ingested_at": datetime.now().isoformat()}
        (self.data_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
        
        print(f"✅ DONE! {file_count} files, {len(points)} vectors stored")
    
    def ingest_prd(self, prd_path: str):
        """Ingest a PRD document (PDF, MD, TXT, DOCX)."""
        from qdrant_client.models import PointStruct
        
        prd_file = Path(prd_path)
        if not prd_file.exists():
            raise ValueError(f"PRD not found: {prd_path}")
        
        print(f"\n📄 INGESTING PRD: {prd_path}")
        
        content = ""
        if prd_path.endswith('.pdf'):
            try:
                from pypdf import PdfReader
                reader = PdfReader(prd_path)
                content = "\n".join([page.extract_text() for page in reader.pages])
            except ImportError:
                print("Install pypdf: pip install pypdf")
                return
        elif prd_path.endswith('.docx'):
            try:
                from docx import Document
                doc = Document(prd_path)
                content = "\n".join([p.text for p in doc.paragraphs])
            except ImportError:
                print("Install python-docx: pip install python-docx")
                return
        else:
            content = prd_file.read_text(encoding='utf-8')
        
        # Chunk the PRD
        chunks = []
        chunk_size = 1500
        header = f"// Document: {prd_file.name}\n// Type: PRD\n\n"
        
        for i in range(0, len(content), chunk_size - 200):
            chunk_content = content[i:i + chunk_size]
            chunks.append(CodeChunk(
                id=hashlib.md5(f"prd:{prd_path}:{i}".encode()).hexdigest(),
                content=header + chunk_content,
                file_path=str(prd_path),
                file_type='prd'
            ))
        
        print(f"📊 Created {len(chunks)} chunks from PRD")
        print("🧠 Generating embeddings...")
        
        points = []
        for i in range(0, len(chunks), 32):
            batch = chunks[i:i + 32]
            embeddings = self.embedder.encode([c.content for c in batch])
            for j, chunk in enumerate(batch):
                points.append(PointStruct(
                    id=hash(chunk.id) % (2**63),
                    vector=embeddings[j].tolist(),
                    payload=chunk.to_dict()
                ))
        
        print("📤 Uploading to Qdrant...")
        for i in range(0, len(points), 100):
            self.qdrant.upsert(collection_name=self.COLLECTION_NAME, points=points[i:i+100])
        
        print(f"✅ PRD ingested! {len(points)} vectors stored")
    
    def ingest_figma_json(self, figma_json_path: str):
        """Ingest Figma export JSON (from Figma API or manual export)."""
        from qdrant_client.models import PointStruct
        
        figma_file = Path(figma_json_path)
        if not figma_file.exists():
            raise ValueError(f"Figma JSON not found: {figma_json_path}")
        
        print(f"\n🎨 INGESTING FIGMA: {figma_json_path}")
        
        figma_data = json.loads(figma_file.read_text())
        
        # Extract meaningful content from Figma structure
        def extract_figma_elements(node, path=""):
            elements = []
            name = node.get('name', '')
            node_type = node.get('type', '')
            current_path = f"{path}/{name}" if path else name
            
            # Extract text content
            if node_type == 'TEXT':
                text = node.get('characters', '')
                if text:
                    elements.append(f"Text: {text} (in {current_path})")
            
            # Extract component info
            if node_type in ['COMPONENT', 'INSTANCE', 'FRAME']:
                elements.append(f"{node_type}: {name}")
            
            # Recurse into children
            for child in node.get('children', []):
                elements.extend(extract_figma_elements(child, current_path))
            
            return elements
        
        elements = []
        if 'document' in figma_data:
            elements = extract_figma_elements(figma_data['document'])
        elif 'children' in figma_data:
            for child in figma_data['children']:
                elements.extend(extract_figma_elements(child))
        else:
            elements = extract_figma_elements(figma_data)
        
        content = "\n".join(elements)
        
        # Chunk
        chunks = []
        chunk_size = 1500
        header = f"// Document: {figma_file.name}\n// Type: Figma Design\n\n"
        
        for i in range(0, len(content), chunk_size - 200):
            chunks.append(CodeChunk(
                id=hashlib.md5(f"figma:{figma_json_path}:{i}".encode()).hexdigest(),
                content=header + content[i:i + chunk_size],
                file_path=str(figma_json_path),
                file_type='figma'
            ))
        
        print(f"📊 Extracted {len(elements)} elements, {len(chunks)} chunks")
        print("🧠 Generating embeddings...")
        
        points = []
        for i in range(0, len(chunks), 32):
            batch = chunks[i:i + 32]
            embeddings = self.embedder.encode([c.content for c in batch])
            for j, chunk in enumerate(batch):
                points.append(PointStruct(
                    id=hash(chunk.id) % (2**63),
                    vector=embeddings[j].tolist(),
                    payload=chunk.to_dict()
                ))
        
        print("📤 Uploading to Qdrant...")
        for i in range(0, len(points), 100):
            self.qdrant.upsert(collection_name=self.COLLECTION_NAME, points=points[i:i+100])
        
        print(f"✅ Figma ingested! {len(points)} vectors stored")

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        query_vector = self.embedder.encode(query).tolist()
        results = self.qdrant.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_vector,
            limit=top_k
        ).points
        return [{"content": r.payload.get("content", ""), "file_path": r.payload.get("file_path", ""),
                 "file_type": r.payload.get("file_type", ""), "score": r.score} for r in results]
    
    def generate_test_cases(self, feature: str) -> Dict:
        print(f"\n🧪 GENERATING TEST CASES for: {feature}")
        
        results = self.search(feature, top_k=15)
        if not results:
            return {"error": "No code found", "test_cases": []}
        
        code_context = "\n\n".join([f"--- {r['file_path']} ---\n{r['content']}" for r in results])
        
        if PROMPT_AVAILABLE:
            prompt = f"{SYSTEM_CONTEXT}\n\n{TEST_CASE_PROMPT}\n\n## CODE CONTEXT\n{code_context}\n\n## FEATURE: {feature}\n\nGenerate 40+ test cases. Return ONLY JSON array."
        else:
            prompt = f"Generate test cases for {feature}. Code:\n{code_context}\n\nReturn JSON array."
        
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text
        
        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text[response_text.find("["):response_text.rfind("]")+1]
            test_cases = json.loads(json_str)
        except Exception:
            (self.output_dir / "raw_response.txt").write_text(response_text)
            return {"error": "JSON parse failed", "test_cases": []}
        
        # Save outputs
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = feature.lower().replace(" ", "_")[:30]
        
        # JSON
        json_file = self.output_dir / f"tc_{slug}_{ts}.json"
        json_file.write_text(json.dumps(test_cases, indent=2))
        
        # CSV
        csv_file = self.output_dir / f"tc_{slug}_{ts}.csv"
        self._save_csv(test_cases, csv_file)
        
        print(f"✅ Generated {len(test_cases)} test cases")
        print(f"📄 JSON: {json_file}")
        print(f"📊 CSV: {csv_file}")
        
        return {"feature": feature, "test_cases": test_cases, "count": len(test_cases),
                "files": {"json": str(json_file), "csv": str(csv_file)}}
    
    def _save_csv(self, test_cases: list, file_path: Path):
        headers = ["Test Case ID", "Priority", "Category", "User Type", "Subscription State",
                   "Subcategory", "Screen Reference", "Precondition", "Test Scenario",
                   "Steps to Execute", "Expected Result", "Dev Status", "QA Status", "Comments"]
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for tc in test_cases:
                writer.writerow([
                    tc.get("test_case_id", ""), tc.get("priority", ""), tc.get("category", ""),
                    tc.get("user_type", ""), tc.get("subscription_state", ""), tc.get("subcategory", ""),
                    tc.get("screen_reference", ""), tc.get("precondition", ""), tc.get("test_scenario", ""),
                    tc.get("steps_to_execute", ""), tc.get("expected_result", ""),
                    "Not Started", "Not Started", tc.get("comments", "")
                ])
    
    def get_stats(self) -> Dict:
        try:
            collection = self.qdrant.get_collection(self.COLLECTION_NAME)
            metadata = json.loads((self.data_dir / "metadata.json").read_text()) if (self.data_dir / "metadata.json").exists() else {}
            return {"status": "connected", "vectors": collection.points_count, **metadata}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def main():
    if len(sys.argv) < 2:
        print("""
╔═══════════════════════════════════════════════════════════════════╗
║         Test Intelligence RAG System                    ║
╠═══════════════════════════════════════════════════════════════════╣
║  INGEST (Add to Knowledge Base - Persistent):                     ║
║    python test_intelligence_rag.py ingest <codebase_path>         ║
║    python test_intelligence_rag.py ingest-prd <prd_file>          ║
║    python test_intelligence_rag.py ingest-figma <figma_json>      ║
║                                                                   ║
║  GENERATE:                                                        ║
║    python test_intelligence_rag.py generate "Feature Name"        ║
║                                                                   ║
║  OTHER:                                                           ║
║    python test_intelligence_rag.py status                         ║
║    python test_intelligence_rag.py search "query"                 ║
╚═══════════════════════════════════════════════════════════════════╝

EXAMPLES:
    # Ingest all sources (do once)
    python test_intelligence_rag.py ingest /path/to/react-native-app
    python test_intelligence_rag.py ingest-prd /path/to/requirements.pdf
    python test_intelligence_rag.py ingest-figma /path/to/figma-export.json
    
    # Generate test cases (uses ALL ingested content)
    python test_intelligence_rag.py generate "Recharge Flow"
    python test_intelligence_rag.py generate "Multi-Profile"
""")
        return
    
    cmd = sys.argv[1]
    rag = TestIntelligenceRAG()
    
    if cmd == "status":
        stats = rag.get_stats()
        print("\n📊 STATUS:")
        for k, v in stats.items():
            print(f"   {k}: {v}")
    
    elif cmd == "ingest" and len(sys.argv) > 2:
        rag.ingest_codebase(sys.argv[2])
    
    elif cmd == "ingest-prd" and len(sys.argv) > 2:
        rag.ingest_prd(sys.argv[2])
    
    elif cmd == "ingest-figma" and len(sys.argv) > 2:
        rag.ingest_figma_json(sys.argv[2])
    
    elif cmd == "generate" and len(sys.argv) > 2:
        result = rag.generate_test_cases(" ".join(sys.argv[2:]))
        if result.get("error"):
            print(f"❌ {result['error']}")
    
    elif cmd == "search" and len(sys.argv) > 2:
        for i, r in enumerate(rag.search(" ".join(sys.argv[2:])), 1):
            print(f"{i}. [{r['file_type']}] {r['file_path']} ({r['score']:.2f})")
    
    else:
        print(f"Unknown command: {cmd}. Run without args for help.")


if __name__ == "__main__":
    main()
