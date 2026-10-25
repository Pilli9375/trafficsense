import os
import json

print("=== TrafficSense Spatiotemporal Graph Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

# Check file
checks['spatiotemporal_graph.py'] = os.path.exists(os.path.join(base, 'src', 'orchestration', 'spatiotemporal_graph.py'))

# Check output
graph_path = os.path.join(base, 'outputs', 'indian_2x2_graph.json')
checks['indian_2x2_graph.json'] = os.path.exists(graph_path)

# Validate graph
graph_ok = False
if checks['indian_2x2_graph.json']:
    try:
        with open(graph_path, 'r') as f:
            data = json.load(f)
        
        print(f"[OK] Graph JSON loaded")
        
        nodes = data.get('nodes', {})
        edges = data.get('edges', {})
        
        print(f"[OK] Nodes: {len(nodes)}")
        print(f"[OK] Edges: {len(edges)}")
        
        # Check Indian characteristics
        has_indian_features = False
        for nid, ndata in nodes.items():
            if ndata.get('has_auto_rickshaw_stand') or ndata.get('road_width_m', 10) < 10:
                has_indian_features = True
                break
        
        print(f"{'[OK]' if has_indian_features else '[FAIL]'} Has Indian features (auto stands / narrow roads)")
        
        # Check I0 neighbors
        i0_neighbors = edges.get('I0', [])
        print(f"[OK] I0 neighbors: {i0_neighbors}")
        checks['i0_has_neighbors'] = len(i0_neighbors) > 0
        
        graph_ok = len(nodes) == 4 and len(edges) == 4 and has_indian_features
        
    except Exception as e:
        print(f"[FAIL] Graph validation error: {e}")

# Print results
passed = sum(1 for v in checks.values() if v)
total = len(checks)
print(f"\nGraph verification: {passed}/{total} checks passed.")
