#!/bin/bash
# Start Ollama server for CoLLMLight integration
export OLLAMA_HOST=0.0.0.0:11434
export OLLAMA_GPU_OVERHEAD=512MB
export OLLAMA_NUM_PARALLEL=2

echo "Starting Ollama server with Gemma 3 4B..."
echo "API endpoint: http://localhost:11434/v1"
echo "Model: gemma3:4b"

ollama serve &

sleep 5

echo "Testing API..."
curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"'

echo ""
echo "Ollama server is running. To stop: pkill ollama"
echo "To test: curl http://localhost:11434/v1/chat/completions ..."

wait
