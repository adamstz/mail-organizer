#!/bin/bash
# Script to start Ollama, ensure model is available, and run classification
# Usage: ./classify_with_ollama.sh [model_name]
# Example: ./classify_with_ollama.sh qwen2.5:0.5b
# Example: ./classify_with_ollama.sh gemma:2b
# Example: ./classify_with_ollama.sh llama3.2

set -e  # Exit on error

# Use provided model or default to qwen2.5:0.5b
MODEL=${1:-qwen2.5:0.5b}

echo "🚀 Starting Ollama email classification..."
echo "📦 Model: $MODEL"
echo ""

# Start Ollama server in background if not already running
if ! pgrep -x "ollama" > /dev/null; then
    echo "📦 Starting Ollama server..."
    ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
    echo "✓ Ollama server started"
else
    echo "✓ Ollama server already running"
fi

# Check if model is available, pull if not
echo ""
echo "🔍 Checking for $MODEL model..."
if ! ollama list | grep -q "$MODEL"; then
    echo "📥 Pulling $MODEL model..."
    ollama pull "$MODEL"
    echo "✓ $MODEL model ready"
else
    echo "✓ $MODEL model already available"
fi

# Export environment variable for the model
export LLM_MODEL=$MODEL

echo ""
echo "🤖 Using model: $LLM_MODEL"
echo "🏃 Starting classification..."
echo ""

# Change to backend directory and run classification
cd "$(dirname "$0")"
make classify
