#!/bin/bash
# Quick setup script for demo preparation

set -e

echo "=========================================="
echo "Agentic AI PoC - Demo Setup"
echo "=========================================="
echo ""

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is not installed. Please install Poetry first:"
    echo "   curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

echo "✅ Poetry found"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
poetry install
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file from .env.example"
        echo "   Please edit .env and add your API keys"
    else
        echo "⚠️  .env.example not found. Creating minimal .env..."
        cat > .env << EOF
# Minimal configuration for demo (Ollama local)
LITELLM_MODEL=ollama/llama3
OLLAMA_BASE_URL=http://127.0.0.1:11434
LINEAR_API_KEY=
DRY_RUN=true
MODE=comment_only
VECTOR_STORE_PATH=./data/lancedb
EMBEDDING_MODEL=local/all-MiniLM-L6-v2
EOF
        echo "✅ Created minimal .env file"
        echo "   Ensure Ollama is running to run the demo"
    fi
else
    echo "✅ .env file exists"
fi
echo ""

# Create data directory
echo "📁 Creating data directory..."
mkdir -p data/lancedb
echo "✅ Data directory created"
echo ""

# Run smoke tests
echo "🧪 Running smoke tests..."
if poetry run python tests/test_smoke.py; then
    echo ""
    echo "✅ Smoke tests passed!"
else
    echo ""
    echo "⚠️  Some smoke tests failed. Check the output above."
fi
echo ""

echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Ensure Ollama is running and .env is configured"
echo "2. (Optional) Add LINEAR_API_KEY for Linear integration"
echo "3. (Optional) Run ingestion: poetry run python scripts/ingest_knowledge.py"
echo "4. Run demo: poetry run python scripts/demo.py"
echo "5. Or start server: poetry run python -m src.main"
echo ""
