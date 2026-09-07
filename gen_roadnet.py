import json

roadnet = {
  "intersections": [
    {
      "id": "I0",
      "point": {"x": 200, "y": 200},
      "width": 8,
      "roads": ["R0", "R1", "R2", "R3", "R0_out", "R1_out", "R2_out", "R3_out"],
      "trafficLight": {
        "lightphases": [
          {"time": 30, "availableRoadLinks": []},
          {"time": 5, "availableRoadLinks": []},
          {"time": 25, "availableRoadLinks": []},
          {"time": 5, "availableRoadLinks": []}
        ],
        "yellowTime": 5
      },
      "virtual": False,
      "roadLinks": []
    },
    {
      "id": "I1",
      "point": {"x": 400, "y": 200},
      "width": 10,
      "roads": ["R1", "R4", "R5", "R6", "R1_out", "R4_out", "R5_out", "R6_out"],
      "trafficLight": {
        "lightphases": [
          {"time": 30, "availableRoadLinks": []},
          {"time": 5, "availableRoadLinks": []},
          {"time": 25, "availableRoadLinks": []},
          {"time": 5, "availableRoadLinks": []}
        ],
        "yellowTime": 5
      },
      "virtual": False,
      "roadLinks": []
    },
    {
      "id": "I2",
      "point": {"x": 200, "y": 400},
      "width": 8,
      "roads": ["R2", "R7", "R8", "R9", "R2_out", "R7_out", "R8_out", "R9_out"],
      "trafficLight": {
        "lightphases": [
          {"time": 30, "availableRoadLinks": []},
          {"time": 5, "availableRoadLinks": []},
          {"time": 25, "availableRoadLinks": []},
          {"time": 5, "availableRoadLinks": []}
        ],
        "yellowTime": 5
      },
      "virtual": False,
      "roadLinks": []
    },
    {
      "id": "I3",
      "point": {"x": 400, "y": 400},
      "width": 10,
      "roads": ["R6", "R9", "R10", "R11", "R6_out", "R9_out", "R10_out", "R11_out"],
      "trafficLight": {
        "lightphases": [
          {"time": 30, "availableRoadLinks": []},
          {"time": 5, "availableRoadLinks": []},
          {"time": 25, "availableRoadLinks": []},
          {"time": 5, "availableRoadLinks": []}
        ],
        "yellowTime": 5
      },
      "virtual": False,
      "roadLinks": []
    }
  ],
  "roads": []
}

# Define coordinates for virtual nodes
coords = {
    "V_0_S": (200, 0), "V_1_S": (400, 0),
    "V_1_E": (600, 200), "V_3_E": (600, 400),
    "V_2_N": (200, 600), "V_3_N": (400, 600),
    "V_0_W": (0, 200), "V_2_W": (0, 400),
    "I0": (200, 200), "I1": (400, 200), "I2": (200, 400), "I3": (400, 400)
}

# Add virtual intersections
for v_id, pt in coords.items():
    if v_id.startswith("V_"):
        roadnet["intersections"].append({
            "id": v_id,
            "point": {"x": pt[0], "y": pt[1]},
            "width": 0,
            "roads": [],
            "trafficLight": {"lightphases": [{"time": 100, "availableRoadLinks": []}], "yellowTime": 0},
            "virtual": True,
            "roadLinks": []
        })

# Helper to add road and its reverse
def add_road(r_id, start_i, end_i, w=2.5, max_s=13.89):
    p1 = coords[start_i]
    p2 = coords[end_i]
    # forward
    r = {
        "id": r_id,
        "points": [{"x": p1[0], "y": p1[1]}, {"x": p2[0], "y": p2[1]}],
        "lanes": [{"width": w, "maxSpeed": max_s}, {"width": w, "maxSpeed": max_s}],
        "startIntersection": start_i,
        "endIntersection": end_i
    }
    roadnet["roads"].append(r)
    # reverse
    r_rev = {
        "id": f"{r_id}_out",
        "points": [{"x": p2[0], "y": p2[1]}, {"x": p1[0], "y": p1[1]}],
        "lanes": [{"width": w, "maxSpeed": max_s}, {"width": w, "maxSpeed": max_s}],
        "startIntersection": end_i,
        "endIntersection": start_i
    }
    roadnet["roads"].append(r_rev)
    
    # update virtual node roads list
    for i in roadnet["intersections"]:
        if i["id"] == start_i:
            if r_id not in i["roads"]: i["roads"].append(r_id)
            if f"{r_id}_out" not in i["roads"]: i["roads"].append(f"{r_id}_out")
        if i["id"] == end_i:
            if r_id not in i["roads"]: i["roads"].append(r_id)
            if f"{r_id}_out" not in i["roads"]: i["roads"].append(f"{r_id}_out")

# I0 roads
add_road("R0", "V_0_S", "I0", 2.5) # South entry to I0
add_road("R1", "I0", "I1", 3.0)    # East to I1
add_road("R2", "I2", "I0", 2.5)    # North from I2 to I0
add_road("R3", "V_0_W", "I0", 2.5) # West entry to I0

# I1 roads
add_road("R4", "V_1_S", "I1", 3.0) # South entry to I1
add_road("R5", "I1", "V_1_E", 3.0) # East exit from I1
add_road("R6", "I3", "I1", 3.0)    # North from I3 to I1

# I2 roads
add_road("R7", "V_2_W", "I2", 2.5) # West entry to I2
add_road("R8", "I2", "V_2_N", 2.5) # North exit from I2
add_road("R9", "I2", "I3", 3.0)    # East to I3

# I3 roads
add_road("R10", "V_3_E", "I3", 3.0) # East exit from I3
add_road("R11", "I3", "V_3_N", 3.0) # North exit from I3

with open(r'C:\Pilli\trafficsense\data\synthetic\indian_2x2_roadnet.json', 'w') as f:
    json.dump(roadnet, f, indent=2)
