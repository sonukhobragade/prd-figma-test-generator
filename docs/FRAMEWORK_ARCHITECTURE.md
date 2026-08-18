# PRD-Figma Test Generator Framework Architecture

> Complete documentation of the AI-powered test case generation framework

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Core Components](#core-components)
4. [RAG System](#rag-system)
5. [Feature Manager](#feature-manager)
6. [Test Generation Pipeline](#test-generation-pipeline)
7. [API Reference](#api-reference)
8. [Frontend Components](#frontend-components)
9. [Data Flow](#data-flow)
10. [Configuration](#configuration)

---

## Overview

The PRD-Figma Test Generator is an AI-powered framework that automatically generates comprehensive test cases from:
- **PRD Documents** (PDF, images)
- **Figma Designs** (via Figma API)
- **Screenshots** (via vision AI)
- **Codebase Context** (via RAG)

### Key Features

- **Multi-source Input**: PRD files, Figma URLs, screenshots, or plain text
- **RAG-Enhanced Generation**: Uses codebase knowledge for smarter test cases
- **Feature-based Document Management**: Links PRDs/Figma to features for reuse
- **Streaming Output**: Real-time test case generation
- **Coverage Analysis**: AI-powered gap detection
- **Multiple Export Formats**: CSV, Markdown checklist

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React + Vite)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │FeatureDropdown│ │FileUploadZone│ │StreamingDemo│ │TestCaseDetailView  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘ │
└─────────┼────────────────┼────────────────┼─────────────────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (FastAPI)                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                           app.py (Main Router)                          ││
│  │  /api/analyze-stream  │  /api/features/*  │  /api/rag/*                ││
│  └───────────┬───────────────────┬────────────────────┬────────────────────┘│
│              │                   │                    │                      │
│  ┌───────────▼───────────┐ ┌─────▼─────────┐ ┌───────▼────────┐            │
│  │   LLM Analyzer        │ │FeatureManager │ │  RAG System    │            │
│  │ (framework/llm_analyzer)│ │(feature_manager)│ │(rag/simple_rag)│            │
│  └───────────┬───────────┘ └───────┬───────┘ └───────┬────────┘            │
│              │                     │                 │                      │
└──────────────┼─────────────────────┼─────────────────┼──────────────────────┘
               │                     │                 │
               ▼                     ▼                 ▼
┌──────────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   LLM Providers      │  │  Qdrant (6335)   │  │  Qdrant (6333)   │
│  ┌────────────────┐  │  │  Feature Docs    │  │  Codebase RAG    │
│  │ OpenAI GPT-4   │  │  │  ┌────────────┐  │  │  ┌────────────┐  │
│  │ Anthropic Claude│  │  │  │app_features│  │  │  │app_  │  │
│  └────────────────┘  │  │  │feature_docs│  │  │  │   code     │  │
└──────────────────────┘  │  └────────────┘  │  │  └────────────┘  │
                          └──────────────────┘  └──────────────────┘
```

---

## Core Components

### 1. Backend (`app.py`)

The main FastAPI application handling:
- PRD/Figma/Screenshot upload and processing
- Streaming test case generation
- Feature management endpoints
- RAG status and sync endpoints

**Key Routes:**
```python
POST /api/analyze-stream    # Stream test case generation
GET  /api/features          # List features
POST /api/features          # Create feature
POST /api/features/{id}/prd # Upload PRD to feature
POST /api/features/{id}/figma # Add Figma to feature
GET  /api/rag/codebase/status # Codebase RAG status
POST /api/rag/codebase/sync   # Sync codebase to RAG
```

### 2. LLM Analyzer (`framework/llm_analyzer.py`)

Orchestrates the test generation process:

```python
class LLMAnalyzer:
    """
    Main analysis engine that:
    1. Processes PRD content
    2. Retrieves codebase context via RAG
    3. Builds enhanced prompts
    4. Streams results from LLM
    """

    def analyze_prd(self, request: TestAnalysisRequest):
        # Step 1: Get static knowledge base context
        kb_context = self.knowledge_base.get_summary_context()

        # Step 2: Get RAG context from codebase
        codebase_context = self.knowledge_base.get_rag_context(query, top_k=8)

        # Step 3: Build system prompt with all context
        system_prompt = self._build_system_prompt(kb_context, codebase_context)

        # Step 4: Stream analysis from LLM
        for chunk in self._stream_analysis(system_prompt, prd_content):
            yield chunk
```

### 3. Knowledge Base (`framework/knowledge_base.py`)

Manages static test generation rules and RAG integration:

```python
class KnowledgeBase:
    """
    Contains:
    - Static test generation rules
    - Best practices and patterns
    - RAG integration for codebase context
    """

    def get_summary_context(self) -> str:
        """Returns static knowledge for prompts"""

    def get_rag_context(self, query: str, top_k: int = 5) -> str:
        """Queries codebase RAG for relevant code snippets"""
```

### 4. Feature Manager (`framework/feature_manager.py`)

Manages features and document relationships:

```python
class FeatureManager:
    """
    Groups PRDs and Figma designs by feature.
    Stores in Qdrant (port 6335) for RAG retrieval.

    Collections:
    - app_features: Feature metadata
    - feature_documents: PRD/Figma content (vectorized)
    """

    def create_feature(name, keywords, description) -> Feature
    def add_document(feature_id, doc_type, name, content) -> FeatureDocument
    def get_feature_context(feature_id) -> Dict  # All PRD + Figma + Code
```

---

## RAG System

### Two Qdrant Instances

| Instance | Port | Purpose | Embeddings |
|----------|------|---------|------------|
| **Codebase RAG** | 6333 | React Native code knowledge | Local (384d, all-MiniLM-L6-v2) |
| **Feature Docs** | 6335 | PRD/Figma documents | OpenAI (1536d, text-embedding-3-small) |

### Codebase RAG (`rag/simple_rag.py`)

Provides code context during test generation:

```python
class SimpleRAG:
    """
    Queries the app_code collection for relevant code.
    Used to enhance test cases with actual implementation knowledge.
    """

    def __init__(self):
        self.collection_name = "app_code"
        self.embedding_provider = "local"  # sentence-transformers
        self.qdrant_port = 6333

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Returns relevant code snippets"""
```

**How it enhances test generation:**
```
PRD: "User should be able to subscribe to premium"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  RAG Query: "subscription premium subscribe"                 │
│                                                              │
│  Results from app_code:                               │
│  ├── SubscriptionScreen.tsx (component structure)           │
│  ├── subscriptionApi.ts (API calls)                         │
│  ├── usePremiumStatus.ts (state management)                 │
│  └── planTypes.ts (data models)                             │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Enhanced Test Cases:                                        │
│  ├── TC_001: Verify subscription API call uses correct endpoint│
│  ├── TC_002: Verify premium status updates after subscription │
│  ├── TC_003: Verify plan selection matches planTypes schema   │
│  └── TC_004: Verify SubscriptionScreen navigation flow        │
└─────────────────────────────────────────────────────────────┘
```

### Feature Document RAG

Stores and retrieves PRD/Figma content:

```python
# When PRD is uploaded to a feature:
def add_prd_to_feature(feature_id, prd_content):
    # 1. Generate embedding
    embedding = openai.embeddings.create(input=prd_content)

    # 2. Store in Qdrant
    qdrant.upsert(
        collection="feature_documents",
        points=[{
            "vector": embedding,
            "payload": {
                "feature_id": feature_id,
                "doc_type": "prd",
                "content": prd_content
            }
        }]
    )

# When generating tests, retrieve related docs:
def get_feature_context(feature_id):
    prds = qdrant.scroll(filter={"feature_id": feature_id, "doc_type": "prd"})
    figmas = qdrant.scroll(filter={"feature_id": feature_id, "doc_type": "figma"})
    return {"prds": prds, "figmas": figmas}
```

---

## Feature Manager

### Purpose

Groups related documents (PRDs, Figma designs) for:
1. **Reuse**: Don't re-upload the same PRD/Figma
2. **RAG Retrieval**: Query past documents for context
3. **Organization**: Feature-based document management

### Data Model

```
Feature
├── id: "feat_subscription_flow"
├── name: "Subscription Flow"
├── keywords: ["subscription", "plan", "premium"]
├── description: "User subscription and payment flows"
├── prd_count: 2
├── figma_count: 3
└── created_at: "2025-01-15T10:00:00Z"

FeatureDocument
├── id: "feat_subscription_flow_prd_abc123"
├── feature_id: "feat_subscription_flow"  ← Links to Feature
├── doc_type: "prd" | "figma"
├── name: "Subscription_PRD_v2.pdf"
├── content: "..." (vectorized)
└── metadata: {file_path, figma_url, ...}
```

### Relationship Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Feature: "Subscription Flow"              │
│                    Keywords: subscription, plan, premium     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │   PRD Docs      │  │   Figma Screens │                   │
│  │                 │  │                 │                   │
│  │ • Subscription  │  │ • Plan Select   │                   │
│  │   PRD v2.pdf    │  │ • Payment Flow  │                   │
│  │ • Edge Cases.pdf│  │ • Success Screen│                   │
│  └────────┬────────┘  └────────┬────────┘                   │
│           │                    │                             │
│           └──────────┬─────────┘                             │
│                      │                                       │
│                      ▼                                       │
│           ┌──────────────────┐                              │
│           │  Codebase RAG    │  ← Auto-queried via keywords │
│           │  (app_code)│                              │
│           │                  │                              │
│           │ • SubscriptionAPI│                              │
│           │ • PaymentService │                              │
│           │ • PlanTypes      │                              │
│           └──────────────────┘                              │
│                      │                                       │
│                      ▼                                       │
│           ┌──────────────────┐                              │
│           │  Test Cases      │  ← Generated with full context│
│           │  (45 tests)      │                              │
│           └──────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Test Generation Pipeline

### Step-by-Step Flow

```
1. USER INPUT
   ├── Select Feature (optional, for RAG)
   ├── Upload PRD / Paste Text
   ├── Add Figma URL (optional)
   └── Upload Screenshot (optional)
           │
           ▼
2. DOCUMENT PROCESSING
   ├── PRD: Extract text (PDF/image OCR)
   ├── Figma: API fetch components & text
   └── Screenshot: Vision AI analysis
           │
           ▼
3. SAVE TO FEATURE (if selected)
   ├── Vectorize documents
   └── Store in Qdrant (port 6335)
           │
           ▼
4. BUILD CONTEXT
   ├── Static Knowledge Base rules
   ├── Codebase RAG query (port 6333)
   └── Feature document context
           │
           ▼
5. LLM ANALYSIS (Streaming)
   ├── System prompt with all context
   ├── User prompt with PRD/Figma content
   └── Stream test cases as generated
           │
           ▼
6. OUTPUT
   ├── Test Cases (streamed to UI)
   ├── Coverage Analysis
   ├── CSV Export
   └── Markdown Checklist
```

### Prompt Structure

```python
SYSTEM_PROMPT = """
You are a test case generation expert.

## Static Knowledge Base
{kb_context}
- Test case format rules
- Priority classification (P0/P1/P2)
- Best practices

## Codebase Context (from RAG)
{codebase_context}
- Relevant code snippets
- API endpoints
- Component structures

## Instructions
Generate comprehensive test cases covering:
- Functional requirements
- Edge cases
- Error scenarios
- User journeys
"""

USER_PROMPT = """
## PRD Content
{prd_content}

## Figma Design Elements
{figma_elements}

## Feature Name
{feature_name}

Generate test cases in the specified format.
"""
```

---

## API Reference

### Test Generation

#### `POST /api/analyze-stream`

Stream test case generation.

**Request:**
```json
{
  "feature_name": "Subscription Flow",
  "prd_text": "...",
  "figma_url": "https://figma.com/file/xxx",
  "llm_provider": "openai" | "anthropic"
}
```

**Response:** Server-Sent Events (SSE)
```
event: status
data: {"message": "Analyzing PRD...", "progress": 10}

event: test_case
data: {"id": "TC_001", "feature": "...", "priority": "P0", ...}

event: complete
data: {"test_cases_count": 45, "coverage_score": 87}
```

### Feature Management

#### `GET /api/features`
List all features.

#### `POST /api/features`
Create a new feature.

**Request:**
```
Content-Type: multipart/form-data

name: "Subscription Flow"
keywords: "subscription, plan, premium"
description: "User subscription flows"
```

#### `POST /api/features/{feature_id}/prd`
Upload PRD to a feature.

**Request:**
```
Content-Type: multipart/form-data

file: <PRD file>
```

#### `POST /api/features/{feature_id}/figma`
Add Figma screen to a feature.

**Request:**
```
Content-Type: multipart/form-data

figma_url: "https://figma.com/file/xxx"
screen_name: "Plan Selection" (optional)
```

#### `GET /api/features/{feature_id}/context`
Get all context for a feature (PRDs + Figma + Codebase).

### RAG Management

#### `GET /api/rag/codebase/status`
Get codebase RAG status.

**Response:**
```json
{
  "enabled": true,
  "health": "healthy",
  "collection": "app_code",
  "documents": 3758,
  "file_count": 450
}
```

#### `POST /api/rag/codebase/sync`
Sync codebase to RAG (re-index).

---

## Frontend Components

### Component Hierarchy

```
App.tsx
├── Header.tsx
├── StreamingDemo.tsx (Main page)
│   ├── CodebaseRAGStatus.tsx
│   ├── FeatureDropdown.tsx
│   ├── FileUploadZone.tsx
│   ├── TestCaseTable.tsx (streaming results)
│   ├── TestCaseMindmap.tsx
│   ├── TestCaseDetailView.tsx
│   └── CoverageInsights.tsx
└── TestRepository.tsx (Browse saved tests)
```

### Key Components

#### `FeatureDropdown.tsx`
Dropdown for selecting/creating features.

```tsx
<FeatureDropdown
  selectedFeature={selectedFeature}
  onSelectFeature={handleFeatureSelect}
  placeholder="Select or create a feature..."
/>
```

#### `StreamingDemo.tsx`
Main analysis interface with:
- Feature selection
- Multi-source input (file/text/figma/screenshot)
- LLM provider selection
- Real-time streaming results
- View modes (mindmap/table/detailed)

#### `TestCaseDetailView.tsx`
Professional test case display with:
- Collapsible sections
- Color-coded priorities
- Dev/QA status tracking
- Copy functionality

---

## Data Flow

### Complete Request Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. User selects feature "Subscription Flow" from dropdown               │
│    → API: GET /api/features                                             │
│    → Feature dropdown shows existing features                           │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. User uploads PRD file                                                │
│    → Frontend: FileUploadZone captures file                             │
│    → File stored in selectedFile state                                  │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. User clicks "Save & Start Analysis"                                  │
│                                                                          │
│    a) Save PRD to feature:                                              │
│       → API: POST /api/features/{id}/prd                                │
│       → Backend: Extract text, vectorize, store in Qdrant (6335)        │
│                                                                          │
│    b) Start streaming analysis:                                          │
│       → API: POST /api/analyze-stream                                   │
│       → Backend: LLMAnalyzer.analyze_prd()                              │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. LLM Analysis Pipeline                                                │
│                                                                          │
│    a) Build context:                                                     │
│       → Static KB: KnowledgeBase.get_summary_context()                  │
│       → Codebase RAG: SimpleRAG.search("subscription plan")             │
│         └─ Qdrant (6333) → Returns relevant code snippets               │
│                                                                          │
│    b) Generate tests:                                                    │
│       → OpenAI/Anthropic API streaming                                  │
│       → Parse chunks into test cases                                    │
│       → Yield via SSE                                                   │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. Frontend receives SSE events                                         │
│                                                                          │
│    → useStreamingAnalysis hook processes events                         │
│    → testCases state updated in real-time                               │
│    → UI renders test cases as they arrive                               │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. Completion                                                           │
│                                                                          │
│    → CSV file saved to output/                                          │
│    → Markdown checklist saved to output/                                │
│    → Coverage analysis displayed                                        │
│    → Download buttons enabled                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration

### Environment Variables (`.env`)

```bash
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Figma API
FIGMA_API_TOKEN=figd_...

# Qdrant (Codebase RAG)
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Qdrant (Feature Documents)
QDRANT_LIGHTRAG_PORT=6335

# Optional: Codebase path for syncing
CODEBASE_PATH=/path/to/react-native-app
```

### Docker Services

```yaml
# docker-compose.yml
services:
  qdrant-codebase:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_codebase_data:/qdrant/storage

  qdrant-features:
    image: qdrant/qdrant:latest
    ports:
      - "6335:6333"
    volumes:
      - qdrant_features_data:/qdrant/storage
```

### Running the Application

```bash
# 1. Start Qdrant instances
docker-compose up -d

# 2. Start backend
cd /path/to/project
source venv/bin/activate
uvicorn app:app --reload --port 8000

# 3. Start frontend
cd frontend
npm run dev
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| RAG returns empty | Wrong collection/embeddings | Check Qdrant port and collection name |
| Feature creation fails | Qdrant not running | Start Qdrant on port 6335 |
| LLM errors | API key missing | Check `.env` file |
| Figma fetch fails | Invalid token | Regenerate Figma API token |

### Debug Commands

```bash
# Check Qdrant status
curl http://localhost:6333/collections
curl http://localhost:6335/collections

# Check codebase RAG
python -c "from rag import SimpleRAG; r = SimpleRAG(); print(r.search('subscription'))"

# Check feature manager
python -c "from framework.feature_manager import get_feature_manager; fm = get_feature_manager(); print(fm.get_status())"
```

---

## Future Enhancements

1. **Test Repository RAG**: Query past test cases for similar features
2. **Auto-Feature Detection**: Automatically suggest features based on PRD content
3. **Coverage Gap Learning**: Learn from missing scenarios across projects
4. **Maestro Integration**: Auto-generate Maestro test scripts
5. **CI/CD Integration**: Run test generation in pipelines

---

*Last Updated: 2025-01-21*
*Version: 2.0.0*
