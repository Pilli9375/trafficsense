"""
CoLLMLight configuration for TrafficSense local LLM.
This file documents the environment variables needed to point CoLLMLight
to the local Ollama server instead of OpenAI GPT-4o.
"""

import os

def setup_local_llm():
    """
    Set environment variables so CoLLMLight uses local Gemma 3 4B.
    Call this before importing or running CoLLMLight code.
    """
    os.environ['OPENAI_API_KEY'] = 'ollama'  # dummy key required by client
    os.environ['OPENAI_BASE_URL'] = 'http://localhost:11434/v1'
    # Optional: override model name if CoLLMLight hardcodes 'gpt-4o'
    # os.environ['COLLM_MODEL'] = 'gemma3:4b'
    print("[Config] CoLLMLight pointed to local Ollama server")
    print(f"[Config] API URL: {os.environ['OPENAI_BASE_URL']}")
    print(f"[Config] Model: gemma3:4b")

if __name__ == '__main__':
    setup_local_llm()
