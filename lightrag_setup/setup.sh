#!/bin/bash
# ============================================
# LightRAG + Qdrant Setup Script
# ============================================
# This script sets up everything you need:
# 1. Installs Python dependencies
# 2. Starts Qdrant via Docker
# 3. Ingests your codebase
# 4. Ready to query!

set -e

echo "================================================"
echo "🚀 LightRAG Test Intelligence Setup"
echo "================================================"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://www.docker.com/products/docker-desktop"
    exit 1
fi

echo "✅ Docker found"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed."
    exit 1
fi

echo "✅ Python 3 found"

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Copy .env if not exists
if [ ! -f ".env" ]; then
    echo ""
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your API keys!"
    echo "   - ANTHROPIC_API_KEY (required)"
    echo "   - OPENAI_API_KEY (optional, for embeddings)"
    echo ""
fi

# Start Qdrant
echo ""
echo "🐳 Starting Qdrant..."
docker-compose up -d

# Wait for Qdrant to be ready
echo "⏳ Waiting for Qdrant to be ready..."
sleep 5

# Check Qdrant health
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "✅ Qdrant is running at http://localhost:6333"
else
    echo "⚠️  Qdrant may still be starting. Wait a moment and try again."
fi

echo ""
echo "================================================"
echo "✅ Setup Complete!"
echo "================================================"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Edit .env file with your API keys:"
echo "   nano .env"
echo ""
echo "2. Ingest your codebase:"
echo "   python rag_system.py ingest /path/to/your/codebase"
echo ""
echo "3. Query for test cases:"
echo "   python rag_system.py query \"What test cases are needed for RechargeScreen?\""
echo ""
echo "4. Generate test cases for a feature:"
echo "   python rag_system.py testcases \"Subscription Flow\""
echo ""
echo "5. Check system status:"
echo "   python rag_system.py status"
echo ""
