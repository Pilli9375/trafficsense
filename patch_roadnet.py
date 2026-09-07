import json
import math

with open(r'C:\Pilli\trafficsense\data\synthetic\indian_2x2_roadnet.json', 'r') as f:
    roadnet = json.load(f)

# Collect all intersection points
nodes = {}
for inter in roadnet.get('intersections', []):
    pt = inter['point']
    nodes[inter['id']] = (pt['x'], pt['y'])

# Find virtual nodes from road endpoints
v_count = 0
for r in roadnet.get('roads', []):
    pts = r['points']
    start_pt = (pts[0]['x'], pts[0]['y'])
    end_pt = (pts[-1]['x'], pts[-1]['y'])
    
    start_id = None
    end_id = None
    
    # Match start
    for nid, pt in nodes.items():
        if math.isclose(pt[0], start_pt[0], abs_tol=1) and math.isclose(pt[1], start_pt[1], abs_tol=1):
            start_id = nid
            break
    
    if not start_id:
        start_id = f"virtual_{v_count}"
        v_count += 1
        nodes[start_id] = start_pt
        roadnet['intersections'].append({
            "id": start_id,
            "point": {"x": start_pt[0], "y": start_pt[1]},
            "width": 0,
            "roads": [],
            "trafficLight": {"lightphases": [], "yellowTime": 0},
            "virtual": True
        })
        
    # Match end
    for nid, pt in nodes.items():
        if math.isclose(pt[0], end_pt[0], abs_tol=1) and math.isclose(pt[1], end_pt[1], abs_tol=1):
            end_id = nid
            break
            
    if not end_id:
        end_id = f"virtual_{v_count}"
        v_count += 1
        nodes[end_id] = end_pt
        roadnet['intersections'].append({
            "id": end_id,
            "point": {"x": end_pt[0], "y": end_pt[1]},
            "width": 0,
            "roads": [],
            "trafficLight": {"lightphases": [], "yellowTime": 0},
            "virtual": True
        })
        
    r['startIntersection'] = start_id
    r['endIntersection'] = end_id

# Update road arrays in intersections
for inter in roadnet['intersections']:
    if 'virtual' not in inter:
        inter['virtual'] = False
    if 'roadLinks' not in inter:
        inter['roadLinks'] = []
    
    # ensure roads list
    if 'roads' not in inter:
        inter['roads'] = []
    
    for r in roadnet['roads']:
        if r['startIntersection'] == inter['id'] or r['endIntersection'] == inter['id']:
            if r['id'] not in inter['roads']:
                inter['roads'].append(r['id'])

with open(r'C:\Pilli\trafficsense\data\synthetic\indian_2x2_roadnet.json', 'w') as f:
    json.dump(roadnet, f, indent=2)
