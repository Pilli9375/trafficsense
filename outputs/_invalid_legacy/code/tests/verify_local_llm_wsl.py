import requests
import json

print("=== WSL Local LLM Verification ===")

try:
    r = requests.post(
        "http://localhost:11434/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json={
            "model": "gemma3:4b",
            "messages": [{"role": "user", "content": "Say 'TrafficSense LLM is ready' and nothing else."}],
            "temperature": 0
        },
        timeout=30
    )
    data = r.json()
    content = data['choices'][0]['message']['content']
    print(f"[OK] Response: {content}")
    if 'ready' in content.lower() or 'trafficsense' in content.lower():
        print("[OK] LLM is responding correctly")
    else:
        print("[WARN] Unexpected response, but API is working")
except Exception as e:
    print(f"[FAIL] {e}")
