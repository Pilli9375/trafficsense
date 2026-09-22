"""
Generate a valid CityFlow 2x2 Indian urban roadnet with proper roadLinks.
This produces a roadnet that CityFlow can actually route vehicles through.
"""
import json
import math

def lerp_points(sx, sy, ex, ey, n=5):
    """Generate n intermediate points along a straight/curved path."""
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append({"x": round(sx + t * (ex - sx), 3), "y": round(sy + t * (ey - sy), 3)})
    return pts

def build_indian_2x2():
    """Build a valid CityFlow 2x2 grid with Indian characteristics."""
    
    spacing = 200  # meters between intersections
    half_w = 8     # half-width of intersection area (used for roadLink geometry)
    num_lanes = 2
    
    # 4 real intersections
    nodes = {
        "I0": (200, 200),  # width=8m (narrow Indian)
        "I1": (400, 200),  # width=10m
        "I2": (200, 400),  # width=8m
        "I3": (400, 400),  # width=10m
    }
    node_widths = {"I0": 8, "I1": 10, "I2": 8, "I3": 10}
    
    # 8 virtual boundary nodes
    boundaries = {
        "B_N0": (200, 0),    # North of I0
        "B_N1": (400, 0),    # North of I1
        "B_E1": (600, 200),  # East of I1
        "B_E3": (600, 400),  # East of I3
        "B_S2": (200, 600),  # South of I2
        "B_S3": (400, 600),  # South of I3
        "B_W0": (0, 200),    # West of I0
        "B_W2": (0, 400),    # West of I2
    }
    
    # Define roads: (road_id, start_node, end_node, lane_width, max_speed)
    # Each road goes from start to end. Vehicles travel in the road's direction.
    # We need bidirectional roads, so we create pairs.
    road_defs = [
        # Boundary-to-I0 and reverse
        ("road_N_I0", "B_N0", "I0", 2.5, 13.89),
        ("road_I0_N", "I0", "B_N0", 2.5, 13.89),
        ("road_W_I0", "B_W0", "I0", 2.5, 13.89),
        ("road_I0_W", "I0", "B_W0", 2.5, 13.89),
        
        # I0 <-> I1 (horizontal)
        ("road_I0_I1", "I0", "I1", 3.0, 13.89),
        ("road_I1_I0", "I1", "I0", 3.0, 13.89),
        
        # Boundary-to-I1 and reverse
        ("road_N_I1", "B_N1", "I1", 3.0, 13.89),
        ("road_I1_N", "I1", "B_N1", 3.0, 13.89),
        ("road_E_I1", "B_E1", "I1", 3.0, 13.89),
        ("road_I1_E", "I1", "B_E1", 3.0, 13.89),
        
        # I0 <-> I2 (vertical)
        ("road_I0_I2", "I0", "I2", 2.5, 13.89),
        ("road_I2_I0", "I2", "I0", 2.5, 13.89),
        
        # I1 <-> I3 (vertical)
        ("road_I1_I3", "I1", "I3", 3.0, 13.89),
        ("road_I3_I1", "I3", "I1", 3.0, 13.89),
        
        # Boundary-to-I2 and reverse
        ("road_W_I2", "B_W2", "I2", 2.5, 13.89),
        ("road_I2_W", "I2", "B_W2", 2.5, 13.89),
        ("road_S_I2", "B_S2", "I2", 2.5, 13.89),
        ("road_I2_S", "I2", "B_S2", 2.5, 13.89),
        
        # I2 <-> I3 (horizontal)
        ("road_I2_I3", "I2", "I3", 3.0, 13.89),
        ("road_I3_I2", "I3", "I2", 3.0, 13.89),
        
        # Boundary-to-I3 and reverse
        ("road_E_I3", "B_E3", "I3", 3.0, 13.89),
        ("road_I3_E", "I3", "B_E3", 3.0, 13.89),
        ("road_S_I3", "B_S3", "I3", 3.0, 13.89),
        ("road_I3_S", "I3", "B_S3", 3.0, 13.89),
    ]
    
    all_coords = {**nodes, **boundaries}
    
    # Build roads JSON
    roads_json = []
    for rid, start, end, lw, ms in road_defs:
        sx, sy = all_coords[start]
        ex, ey = all_coords[end]
        roads_json.append({
            "id": rid,
            "startIntersection": start,
            "endIntersection": end,
            "points": [{"x": sx, "y": sy}, {"x": ex, "y": ey}],
            "lanes": [{"width": lw, "maxSpeed": ms} for _ in range(num_lanes)]
        })
    
    # Build a lookup: for each intersection, which roads are incoming and outgoing?
    incoming = {}  # node_id -> list of road_ids ending here
    outgoing = {}  # node_id -> list of road_ids starting here
    road_map = {}  # road_id -> road_def tuple
    
    for rd in road_defs:
        rid, start, end, lw, ms = rd
        road_map[rid] = rd
        incoming.setdefault(end, []).append(rid)
        outgoing.setdefault(start, []).append(rid)
    
    # Determine road direction (angle from start to end)
    def road_angle(rid):
        _, start, end, _, _ = road_map[rid]
        sx, sy = all_coords[start]
        ex, ey = all_coords[end]
        return math.atan2(ey - sy, ex - sx)
    
    # For each real intersection, generate roadLinks
    def make_road_links(node_id):
        """Generate roadLinks for a real intersection.
        
        For each incoming road, create links to each outgoing road (except the reverse).
        """
        inc = incoming.get(node_id, [])
        out = outgoing.get(node_id, [])
        
        links = []
        for in_road in inc:
            in_angle = road_angle(in_road)
            _, in_start, _, _, _ = road_map[in_road]
            
            for out_road in out:
                _, _, out_end, _, _ = road_map[out_road]
                
                # Skip U-turn (going back to where we came from)
                if out_end == in_start:
                    continue
                
                out_angle = road_angle(out_road)
                
                # Determine turn type based on angle difference
                angle_diff = (out_angle - in_angle + math.pi) % (2 * math.pi) - math.pi
                if abs(angle_diff) < 0.3:
                    turn_type = "go_straight"
                elif angle_diff > 0:
                    turn_type = "turn_left"
                else:
                    turn_type = "turn_right"
                
                # Generate lane links with simple straight-line points
                # (CityFlow accepts simple paths; complex Bezier curves are optional)
                lane_links = []
                for sl in range(num_lanes):
                    for el in range(num_lanes):
                        # Simple lane link: start lane -> end lane with straight path
                        lane_links.append({
                            "startLaneIndex": sl,
                            "endLaneIndex": el,
                            "points": []  # empty points = CityFlow computes default path
                        })
                
                links.append({
                    "type": turn_type,
                    "startRoad": in_road,
                    "endRoad": out_road,
                    "direction": 0,
                    "laneLinks": lane_links
                })
        
        return links
    
    # Build intersections JSON
    intersections_json = []
    
    for nid, (nx, ny) in nodes.items():
        road_links = make_road_links(nid)
        
        # Build phases: phase 0 = NS green, phase 1 = yellow, phase 2 = EW green, phase 3 = yellow
        # Map roadLinks to NS vs EW based on incoming road direction
        ns_links = []
        ew_links = []
        for i, rl in enumerate(road_links):
            in_road = rl["startRoad"]
            angle = road_angle(in_road)
            # Vertical roads (NS): angle ~ pi/2 or -pi/2
            if abs(abs(angle) - math.pi / 2) < 0.5:
                ns_links.append(i)
            else:
                ew_links.append(i)
        
        all_roads = list(set(
            [r for r in incoming.get(nid, [])] + [r for r in outgoing.get(nid, [])]
        ))
        
        intersections_json.append({
            "id": nid,
            "point": {"x": nx, "y": ny},
            "width": node_widths[nid],
            "roads": all_roads,
            "roadLinks": road_links,
            "trafficLight": {
                "lightphases": [
                    {"time": 30, "availableRoadLinks": ns_links},
                    {"time": 5, "availableRoadLinks": []},
                    {"time": 25, "availableRoadLinks": ew_links},
                    {"time": 5, "availableRoadLinks": []}
                ],
                "yellowTime": 5
            },
            "virtual": False
        })
    
    # Add virtual boundary intersections
    for bid, (bx, by) in boundaries.items():
        b_roads = list(set(
            [r for r in incoming.get(bid, [])] + [r for r in outgoing.get(bid, [])]
        ))
        intersections_json.append({
            "id": bid,
            "point": {"x": bx, "y": by},
            "width": 0,
            "roads": b_roads,
            "roadLinks": [],
            "trafficLight": {
                "lightphases": [{"time": 10000, "availableRoadLinks": []}],
                "yellowTime": 0
            },
            "virtual": True
        })
    
    roadnet = {
        "intersections": intersections_json,
        "roads": roads_json
    }
    
    return roadnet


def build_indian_flow():
    """Build flow file with Indian vehicle mix."""
    flow = [
        # Cars (length=4m, gap=0.5m) - North to East through I0->I1
        {
            "vehicle": {"length": 4.0, "width": 1.8, "maxPosAcc": 2.0, "maxNegAcc": 4.5,
                        "usualPosAcc": 2.0, "usualNegAcc": 4.5, "minGap": 0.5,
                        "maxSpeed": 13.89, "headwayTime": 1.2},
            "route": ["road_N_I0", "road_I0_I1", "road_I1_E"],
            "interval": 3.0, "startTime": 0, "endTime": 3600
        },
        # Auto-rickshaws (length=2.5m, gap=0.3m) - West to South through I0->I2
        {
            "vehicle": {"length": 2.5, "width": 1.3, "maxPosAcc": 2.5, "maxNegAcc": 5.0,
                        "usualPosAcc": 2.5, "usualNegAcc": 5.0, "minGap": 0.3,
                        "maxSpeed": 11.11, "headwayTime": 0.8},
            "route": ["road_W_I0", "road_I0_I2", "road_I2_S"],
            "interval": 1.5, "startTime": 0, "endTime": 3600
        },
        # Motorcycles (length=1.5m, gap=0.2m) - North to East through I0->I1
        {
            "vehicle": {"length": 1.5, "width": 0.8, "maxPosAcc": 3.0, "maxNegAcc": 6.0,
                        "usualPosAcc": 3.0, "usualNegAcc": 6.0, "minGap": 0.2,
                        "maxSpeed": 11.11, "headwayTime": 0.5},
            "route": ["road_N_I0", "road_I0_I1", "road_I1_E"],
            "interval": 1.0, "startTime": 0, "endTime": 3600
        },
        # Bus (length=10m, gap=1.0m) - West to West through I0->I1->I3->I2
        {
            "vehicle": {"length": 10.0, "width": 2.5, "maxPosAcc": 1.5, "maxNegAcc": 3.5,
                        "usualPosAcc": 1.5, "usualNegAcc": 3.5, "minGap": 1.0,
                        "maxSpeed": 11.11, "headwayTime": 2.0},
            "route": ["road_W_I0", "road_I0_I1", "road_I1_E"],
            "interval": 8.0, "startTime": 0, "endTime": 3600
        },
        # Cars - North I1 to East I1
        {
            "vehicle": {"length": 4.0, "width": 1.8, "maxPosAcc": 2.0, "maxNegAcc": 4.5,
                        "usualPosAcc": 2.0, "usualNegAcc": 4.5, "minGap": 0.5,
                        "maxSpeed": 13.89, "headwayTime": 1.2},
            "route": ["road_N_I1", "road_I1_I3", "road_I3_E"],
            "interval": 3.5, "startTime": 0, "endTime": 3600
        },
        # Auto-rickshaws - West I2 to East I3
        {
            "vehicle": {"length": 2.5, "width": 1.3, "maxPosAcc": 2.5, "maxNegAcc": 5.0,
                        "usualPosAcc": 2.5, "usualNegAcc": 5.0, "minGap": 0.3,
                        "maxSpeed": 11.11, "headwayTime": 0.8},
            "route": ["road_W_I2", "road_I2_I3", "road_I3_E"],
            "interval": 1.5, "startTime": 0, "endTime": 3600
        },
        # Motorcycles - South I2 to North I0
        {
            "vehicle": {"length": 1.5, "width": 0.8, "maxPosAcc": 3.0, "maxNegAcc": 6.0,
                        "usualPosAcc": 3.0, "usualNegAcc": 6.0, "minGap": 0.2,
                        "maxSpeed": 11.11, "headwayTime": 0.5},
            "route": ["road_S_I2", "road_I2_I0", "road_I0_N"],
            "interval": 1.0, "startTime": 0, "endTime": 3600
        },
        # Cars - South I3 to West I2
        {
            "vehicle": {"length": 4.0, "width": 1.8, "maxPosAcc": 2.0, "maxNegAcc": 4.5,
                        "usualPosAcc": 2.0, "usualNegAcc": 4.5, "minGap": 0.5,
                        "maxSpeed": 13.89, "headwayTime": 1.2},
            "route": ["road_S_I3", "road_I3_I2", "road_I2_W"],
            "interval": 4.0, "startTime": 0, "endTime": 3600
        },
    ]
    return flow


def build_config():
    """Build CityFlow config pointing to the generated files."""
    return {
        "interval": 1.0,
        "seed": 42,
        "dir": "",
        "roadnetFile": "",
        "flowFile": "",
        "rlTrafficLight": True,
        "saveReplay": False,
        "roadnetLogFile": "",
        "replayLogFile": ""
    }


if __name__ == "__main__":
    import os
    
    # Determine project root (this script is in scripts/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    out_dir = os.path.join(project_root, 'data', 'synthetic')
    os.makedirs(out_dir, exist_ok=True)
    
    # Generate roadnet
    roadnet = build_indian_2x2()
    roadnet_path = os.path.join(out_dir, 'indian_2x2_roadnet.json')
    with open(roadnet_path, 'w') as f:
        json.dump(roadnet, f, indent=2)
    
    # Count stats
    real_nodes = [i for i in roadnet['intersections'] if not i.get('virtual', False)]
    total_road_links = sum(len(i.get('roadLinks', [])) for i in real_nodes)
    print(f"Roadnet: {len(real_nodes)} real intersections, {len(roadnet['roads'])} roads, {total_road_links} roadLinks")
    
    # Generate flow
    flow = build_indian_flow()
    flow_path = os.path.join(out_dir, 'indian_2x2_flow.json')
    with open(flow_path, 'w') as f:
        json.dump(flow, f, indent=2)
    print(f"Flow: {len(flow)} vehicle definitions")
    
    # Generate config with absolute WSL path for CityFlow
    config = build_config()
    wsl_dir = out_dir.replace('\\', '/').replace('C:', '/mnt/c')
    config["dir"] = wsl_dir + "/"
    config["roadnetFile"] = "indian_2x2_roadnet.json"
    config["flowFile"] = "indian_2x2_flow.json"
    config_path = os.path.join(out_dir, 'indian_2x2_config.json')
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Config: {config_path}")
    
    print("Done! Files written to:", out_dir)
