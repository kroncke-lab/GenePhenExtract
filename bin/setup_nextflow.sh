#!/bin/bash
# Setup script for GenePhenExtract Nextflow pipeline

set -e

echo "=========================================="
echo "GenePhenExtract Nextflow Setup"
echo "=========================================="
echo

# Check if Nextflow is installed
if ! command -v nextflow &> /dev/null; then
    echo "Installing Nextflow..."
    curl -s https://get.nextflow.io | bash
    sudo mv nextflow /usr/local/bin/ 2>/dev/null || {
        echo "Note: Could not move to /usr/local/bin (needs sudo)"
        echo "Nextflow installed in current directory"
        echo "Add to PATH or move manually: sudo mv nextflow /usr/local/bin/"
    }
else
    echo "✓ Nextflow already installed: $(nextflow -version | head -1)"
fi

echo

# Check for Docker
if command -v docker &> /dev/null; then
    echo "✓ Docker found: $(docker --version)"

    # Offer to build Docker image
    read -p "Build Docker image for GenePhenExtract? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Building Docker image..."
        docker build -t genephenextract:latest .
        echo "✓ Docker image built successfully"
    fi
else
    echo "⚠ Docker not found (optional but recommended)"
    echo "  Install: https://docs.docker.com/get-docker/"
fi

echo

# Check for API keys
echo "Checking API keys..."

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠ ANTHROPIC_API_KEY not set"
    echo "  For Claude: export ANTHROPIC_API_KEY='your-key'"
else
    echo "✓ ANTHROPIC_API_KEY is set"
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠ OPENAI_API_KEY not set"
    echo "  For OpenAI: export OPENAI_API_KEY='your-key'"
else
    echo "✓ OPENAI_API_KEY is set"
fi

if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠ GOOGLE_API_KEY not set"
    echo "  For Gemini: export GOOGLE_API_KEY='your-key'"
else
    echo "✓ GOOGLE_API_KEY is set"
fi

echo

# Create sample genes.txt if it doesn't exist
if [ ! -f genes.txt ]; then
    echo "Creating sample genes.txt..."
    cat > genes.txt <<EOF
# Sample gene list for testing
# Add your genes here (one per line)

KCNH2
SCN5A
KCNQ1
EOF
    echo "✓ Created genes.txt with sample genes"
else
    echo "✓ genes.txt already exists"
fi

echo
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo
echo "Next steps:"
echo "1. Edit genes.txt with your genes of interest"
echo "2. Set an API key (Claude, OpenAI, or Gemini)"
echo "3. Run test: nextflow run main.nf -profile test --genes genes.txt"
echo "4. Run full pipeline: nextflow run main.nf --genes genes.txt --llm_provider claude"
echo
echo "For help: see docs/NEXTFLOW_PIPELINE.md"
echo
