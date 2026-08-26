import requests
import json
import sys

print("=== TrafficSense Local LLM Verification ===")

# Test Ollama API from Windows (via WSL localhost forwarding)
url = "http://localhost:11434/v1/chat/completions"

try:
    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "model": "gemma3:4b",
            "messages": [
                {"role": "system", "content": "You are a traffic signal controller in an Indian city."},
                {"role": "user", "content": "Intersection I0 has 12 cars, 5 auto-rickshaws, and high congestion. Neighbor I1 has low congestion. What cooperative signal timing do you recommend? Keep it brief."}
            ],
            "temperature": 0.5,
            "max_tokens": 150
        },
        timeout=60
    )
    
    if response.status_code == 200:
        data = response.json()
        content = data['choices'][0]['message']['content']
        print("[OK] API responded with status 200")
        print(f"[OK] Model response received ({len(content)} chars)")
        print(f"\n--- Model Response ---\n{content}\n---")
        
        # Check for reasoning keywords
        reasoning_keywords = ['green', 'red', 'phase', 'timing', 'seconds', 'queue', 'congestion', 'cooperat', 'neighbor']
        found = [kw for kw in reasoning_keywords if kw.lower() in content.lower()]
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
