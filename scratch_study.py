import cityflow
import json

config_path = '/mnt/c/Pilli/trafficsense/data/synthetic/indian_2x2_config.json'
eng = cityflow.Engine(config_path, thread_num=1)

# Run a few steps to get vehicles
for _ in range(50):
    eng.next_step()

# Get lane names and vehicle counts
lane_vehicles = eng.get_lane_vehicle_count()
lane_waiting = eng.get_lane_waiting_vehicle_count()

print("=== Lane Vehicle Counts (non-zero) ===")
for lane, count in sorted(lane_vehicles.items()):
    if count > 0:
        print(f"  {lane}: {count} vehicles")

print(f"\nTotal lanes: {len(lane_vehicles)}")
print(f"Total vehicles: {sum(lane_vehicles.values())}")

# Show lane naming pattern
print("\n=== All Lane Names (first 20) ===")
for lane in sorted(lane_vehicles.keys())[:20]:
    print(f"  {lane}")

# Load roadnet to understand lane-to-intersection mapping
with open('/mnt/c/Pilli/trafficsense/data/synthetic/indian_2x2_roadnet.json') as f:
    rn = json.load(f)

print("\n=== Road-to-Intersection Mapping ===")
for inter in rn['intersections']:
    if not inter.get('virtual', False):
        incoming = []
        outgoing = []
        for road in rn['roads']:
            if road['endIntersection'] == inter['id']:
                incoming.append(road['id'])
            elif road['startIntersection'] == inter['id']:
                outgoing.append(road['id'])
        print(f"\n{inter['id']}:")
        print(f"  Incoming: {incoming}")
        print(f"  Outgoing: {outgoing}")
