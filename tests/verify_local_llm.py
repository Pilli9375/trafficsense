import requests
import json
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src import config

target_model = getattr(config, 'OLLAMA_MODEL', 'gemma4:e4b')
print("=== TrafficSense Local LLM Verification ===")
print(f"Target Model: {target_model}")

# Test Ollama API from Windows
url = f"{config.OLLAMA_BASE_URL}/chat/completions"

try:
    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "model": target_model,
            "messages": [
                {"role": "system", "content": "You are a traffic signal controller in an Indian city."},
                {"role": "user", "content": "Intersection I0 has 12 cars, 5 auto-rickshaws, and high congestion. Neighbor I1 has low congestion. What cooperative signal timing do you recommend? Keep it brief."}
            ],
            "temperature": 0.5,
            "max_tokens": 600
        },
        timeout=120
    )
    
    if response.status_code == 200:
        data = response.json()
        msg = data['choices'][0]['message']
        content = msg.get('content') or ''
        reasoning = msg.get('reasoning') or ''
        combined = (content + "\n" + reasoning).strip()
        print("[OK] API responded with status 200")
        print(f"[OK] Content received: {len(content)} chars | Thinking trace: {len(reasoning)} chars")
        if content:
            print(f"\n--- Model Response ---\n{content}\n---")
        if reasoning:
            print(f"\n--- Thinking Trace (Snippet) ---\n{reasoning[:300]}...\n---")
        
        # Check for reasoning keywords
        reasoning_keywords = ['green', 'red', 'phase', 'timing', 'seconds', 'queue', 'congestion', 'cooperat', 'neighbor', 'i0', 'i1']
        found = [kw for kw in reasoning_keywords if kw.lower() in combined.lower()]
        print(f"[OK] Reasoning keywords found: {found}")
        
    else:
        print(f"[FAIL] API returned status {response.status_code}")
        print(response.text)
        
except requests.exceptions.ConnectionError:
    print("[FAIL] Could not connect to Ollama server at localhost:11434")
    print("[INFO] Make sure Ollama is running in WSL: ollama serve")
    sys.exit(1)
except Exception as e:
    print(f"[FAIL] Error: {e}")
    sys.exit(1)

print("\nLocal LLM verification complete.")
