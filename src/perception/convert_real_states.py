import json
from state_exporter import PerceptionToCoLLMLight

# Load perception states
with open(r'C:\Pilli\trafficsense\outputs\perception_demo\perception_states.json', 'r') as f:
    states = json.load(f)

if states:
    last_state = states[-1]
    exporter = PerceptionToCoLLMLight(intersection_id='I0', lane_count=4)
    collm_state = exporter.convert(last_state, current_phase=0)
    
    output_path = r'C:\Pilli\trafficsense\outputs\perception_demo\collmlight_state.json'
    exporter.save(collm_state, output_path)
    
    print("Converted real perception state to CoLLMLight format:")
    print(json.dumps(collm_state, indent=2))
else:
    print("No perception states found.")
