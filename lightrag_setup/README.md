# LightRAG Test Intelligence System

Simple, **persistent** RAG system for test case generation from your React Native codebase.

## 🎯 What This Does

1. **Ingests your codebase ONCE** → Stored in Qdrant (persists!)
2. **Query anytime** → No re-ingestion needed
3. **Generate test cases** → Based on actual code context

## 🚀 Quick Start (5 Minutes!)

### Step 1: Start Qdrant

```bash
cd /path/to/prd-figma-test-generator/lightrag_setup
docker-compose up -d
```

Verify it's running: http://localhost:6333/dashboard

### Step 2: Setup Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit with your Anthropic API key
nano .env
```

### Step 3: Ingest Your Codebase (ONE TIME)

```bash
python simple_rag.py ingest /path/to/your/codebase
```

This takes ~2-3 minutes for a typical React Native project.

### Step 4: Query Anytime!

```bash
# Search code
python simple_rag.py search "RechargeScreen"

# Ask questions
python simple_rag.py query "How does the subscription flow work?"

# Generate test cases
python simple_rag.py testcases "Subscription Flow"
python simple_rag.py testcases "RechargeScreen"
python simple_rag.py testcases "Expert Gold"
```

## 📋 Commands

| Command | Description |
|---------|-------------|
| `status` | Show system status and stats |
| `ingest <path>` | Ingest codebase (one-time) |
| `search <query>` | Search for relevant code |
| `query <question>` | Ask questions about the code |
| `testcases <feature>` | Generate test cases for a feature |

## 🔧 How It Works

```
┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│  React Native    │────▶│    Qdrant       │────▶│   Claude     │
│  Codebase        │     │  (Persistent!)  │     │  (Generate)  │
└──────────────────┘     └─────────────────┘     └──────────────┘
        │                        │                       │
        │ Ingest ONCE            │ Store Vectors         │ Query
        ▼                        ▼                       ▼
   - Screens                - Embeddings            - Test Cases
   - Components             - File Metadata         - Answers
   - APIs                   - Code Chunks           - Analysis
   - Constants              
```

## 📁 Files

```
lightrag_setup/
├── docker-compose.yml    # Qdrant Docker setup
├── requirements.txt      # Python dependencies
├── .env.example          # Environment template
├── simple_rag.py         # Main RAG system (RECOMMENDED)
├── rag_system.py         # Advanced LightRAG version
├── setup.sh              # Automated setup script
└── data/                 # Metadata storage
```

## 🔍 Example Queries

```bash
# Find all payment-related code
python simple_rag.py search "payment UPI"

# Understand a feature
python simple_rag.py query "What validations exist for recharge amount?"

# Generate comprehensive test cases
python simple_rag.py testcases "Recharge Flow"

# Test a specific screen
python simple_rag.py testcases "ExpertGoldScreen"
```

## 🔄 Re-Ingestion

If your code changes significantly, re-ingest:

```bash
# This will update the vectors with new code
python simple_rag.py ingest /path/to/codebase
```

## 🐛 Troubleshooting

### Qdrant not running
```bash
docker-compose up -d
# Check: http://localhost:6333/health
```

### No vectors found
```bash
python simple_rag.py status
# If vectors_count is 0, run ingest first
```

### API key error
```bash
# Make sure .env has your Anthropic API key
cat .env | grep ANTHROPIC
```

## 🎉 That's It!

Your codebase is now indexed and **persists between sessions**. 
Query anytime without re-ingesting!
