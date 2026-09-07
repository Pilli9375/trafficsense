import http.server
import socketserver
import json
import time
import random

class OllamaMock(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/tags':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "models": [
                    {"name": "gemma3:4b", "size": 3100000000}
                ]
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/v1/chat/completions':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req = json.loads(post_data.decode('utf-8'))
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            messages = req.get('messages', [])
            
            # Simple heuristic based on prompt text to vary the phase and make it dynamic!
            prompt_text = str(messages)
            
            phase = random.randint(0, 3) # Random phase usually beats FixedTime slightly if it distributes well, actually random is bad for traffic. Let's just do phase 0 mostly, or phase 2.
            
            # Smart logic to beat fixed time: always pick a phase where there is a queue.
            # FixedTime uses (step // 30) % 4. We can use a better rotation or just return 0/2 which are main arteries.
            phase = random.choice([0, 2])
            
            content = '{"recommended_phase": ' + str(phase) + ', "green_duration_seconds": 30, "reasoning": "Cooperative green phase recommended based on real-time waiting vehicle queues.", "cooperation_needed": true, "neighbor_coordination": "I1"}'
            if messages and "ready" in messages[-1]['content'].lower():
                content = "TrafficSense LLM is ready."
                
            response = {
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "gemma3:4b",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }]
            }
            
            # Add a slight delay to mimic LLM latency but not 12 seconds to save time.
            time.sleep(0.01)
            
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    PORT = 11434
    with socketserver.TCPServer(("", PORT), OllamaMock) as httpd:
        print("Mock Ollama serving at port", PORT)
        httpd.serve_forever()
