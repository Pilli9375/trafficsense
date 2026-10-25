import os
import json

print("=== TrafficSense Indian Scenario Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

# Check files
files = [
    'data/synthetic/indian_2x2_roadnet.json',
    'data/synthetic/indian_2x2_flow.json',
    'data/synthetic/indian_2x2_config.json'
]

for f in files:
    checks[f] = os.path.exists(os.path.join(base, f))
    print(f"{'[OK]' if checks[f] else '[FAIL]'} {f}")

# Validate roadnet
roadnet_ok = False
if checks.get('data/synthetic/indian_2x2_roadnet.json'):
    try:
        with open(os.path.join(base, 'data/synthetic/indian_2x2_roadnet.json'), 'r') as f:
            roadnet = json.load(f)
        
        intersections = roadnet.get('intersections', [])
        roads = roadnet.get('roads', [])
        
        print(f"[OK] Roadnet: {len(intersections)} intersections, {len(roads)} roads")
        
        # Check Indian width
        widths = [i.get('width', 12) for i in intersections if not i.get('virtual', False)]
        avg_width = sum(widths) / len(widths) if widths else 0
        print(f"[INFO] Avg road width: {avg_width:.1f}m")
        checks['indian_width'] = avg_width <= 10.0
        
        # Check 4 intersections (ignoring virtual ones I added)
        real_intersections = [i for i in intersections if not i.get('virtual', False)]
        checks['four_intersections'] = len(real_intersections) == 4
        
        roadnet_ok = len(real_intersections) == 4 and len(roads) >= 8
        
    except Exception as e:
        print(f"[FAIL] Roadnet error: {e}")

# Validate flow
flow_ok = False
if checks.get('data/synthetic/indian_2x2_flow.json'):
    try:
        with open(os.path.join(base, 'data/synthetic/indian_2x2_flow.json'), 'r') as f:
            flow = json.load(f)
        
        print(f"[OK] Flow: {len(flow)} entries")
        
        # Check for tight gaps
        tight_gaps = sum(1 for entry in flow if entry.get('vehicle', {}).get('minGap', 2.5) < 1.0)
        print(f"[OK] Entries with tight gaps (<1m): {tight_gaps}")
        checks['tight_gaps'] = tight_gaps > 0
        
        # Check for motorcycles (small vehicles)
        small_vehicles = sum(1 for entry in flow if entry.get('vehicle', {}).get('length', 4) < 2.0)
        print(f"[OK] Small vehicle entries (motorcycles/autos): {small_vehicles}")
        checks['mixed_vehicles'] = small_vehicles > 0
        
        flow_ok = len(flow) >= 4
        
    except Exception as e:
        print(f"[FAIL] Flow error: {e}")

# Print results
passed = sum(1 for v in checks.values() if v)
total = len(checks)
print(f"\nIndian scenario verification: {passed}/{total} checks passed.")
