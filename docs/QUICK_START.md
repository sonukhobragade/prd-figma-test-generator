# Quick Start Guide

> Get up and running with the PRD-Figma Test Generator in 5 minutes

## Prerequisites

- Python 3.9+
- Node.js 18+
- Docker (for Qdrant)
- OpenAI or Anthropic API key
- Figma API token (optional, for Figma designs)

## 1. Start Services

```bash
# Start Qdrant instances (RAG storage)
docker-compose up -d

# Verify Qdrant is running
curl http://localhost:6333/health  # Codebase RAG
curl http://localhost:6335/health  # Feature Documents
```

## 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your API keys
nano .env
```

Required variables:
```bash
OPENAI_API_KEY=sk-...           # For GPT-4 and embeddings
# OR
ANTHROPIC_API_KEY=sk-ant-...    # For Claude

# Optional
FIGMA_API_TOKEN=figd_...        # For Figma integration
```

## 3. Start Backend

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Start server
uvicorn app:app --reload --port 8000
```

## 4. Start Frontend

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start dev server
npm run dev
```

Open http://localhost:3002

---

## Basic Usage

### Generate Test Cases (No Feature Linking)

1. Enter a **Feature Name** (e.g., "User Login")
2. Upload a **PRD file** (PDF or image) OR paste text
3. Optionally add a **Figma URL**
4. Click **Start Analysis**
5. Watch test cases stream in real-time
6. Download CSV or Markdown when complete

### Generate Test Cases (With Feature Linking)

1. Click the **Feature dropdown**
2. Select an existing feature OR create new:
   - Name: "Subscription Flow"
   - Keywords: "subscription, plan, premium"
3. Upload PRD / Add Figma URL
4. Click **Save & Start Analysis**
5. Documents are saved for future RAG retrieval

---

## Feature Management

### Create a Feature

Features group related PRDs and Figma designs:

```
Feature: "Subscription Flow"
├── Keywords: subscription, plan, premium
├── PRDs:
│   ├── Subscription_PRD_v2.pdf
│   └── Edge_Cases.pdf
└── Figma:
    ├── Plan Selection Screen
    └── Payment Confirmation
```

### Benefits of Features

1. **No Re-upload**: Reuse PRDs/Figma across sessions
2. **Better Context**: RAG queries past documents
3. **Organization**: Group related test artifacts

---

## View Modes

### Mindmap View
Visual hierarchy of test cases by category

### Table View
Quick scan with priority filters

### Detailed View
Professional format with:
- Collapsible sections
- Color-coded priorities (P0/P1/P2)
- Test steps as numbered list
- Expected results as bullet points

---

## Tips for Best Results

### PRD Quality

**Good PRD:**
```
## Feature: Premium Subscription

### Requirements
1. User can view available plans (Monthly, Yearly)
2. User can select a plan and proceed to payment
3. Payment supports UPI, Card, and Net Banking
4. On success, show confirmation with plan details
5. Update user's premium status immediately

### Edge Cases
- User already has an active subscription
- Payment fails midway
- Network disconnection during payment
```

**Bad PRD:**
```
Make subscription work
```

### Combine Inputs for Best Results

| Input Combination | Accuracy |
|-------------------|----------|
| PRD only | Good |
| PRD + Figma | Better |
| PRD + Figma + Codebase RAG | Best |

### Use Specific Feature Names

**Good:** "User Login with OTP"
**Bad:** "Login Feature"

---

## Codebase RAG

### What It Does

Queries your React Native codebase to enhance test cases with:
- Actual component names
- API endpoint patterns
- State management flows
- Error handling patterns

### Sync Your Codebase

1. Set `CODEBASE_PATH` in `.env`
2. Click "Sync Codebase" in the UI
3. Wait for indexing to complete

### Check Status

The UI shows codebase RAG status:
- Green = Healthy, X files indexed
- Yellow = Offline
- Red = Error

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + Enter` | Start Analysis |
| `Ctrl/Cmd + K` | Clear all inputs |

---

## Troubleshooting

### "Failed to connect to Qdrant"

```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Restart Qdrant
docker-compose restart
```

### "LLM analysis failed"

1. Check API key in `.env`
2. Verify API quota/credits
3. Try switching provider (OpenAI ↔ Anthropic)

### "Figma fetch failed"

1. Check Figma token in `.env`
2. Ensure URL is a valid Figma file/frame URL
3. Verify you have access to the Figma file

### "No codebase context"

1. Check Qdrant on port 6333
2. Verify collection `app_code` exists
3. Run codebase sync

---

## Next Steps

- Read [FRAMEWORK_ARCHITECTURE.md](./FRAMEWORK_ARCHITECTURE.md) for deep dive
- Explore the API at http://localhost:8000/docs
- Set up Maestro integration for automated testing

---

*Happy Testing!*
