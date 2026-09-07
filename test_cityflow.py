import cityflow
import json
config_path = '/mnt/c/Pilli/trafficsense/data/synthetic/indian_2x2_config.json'
print('Loading Indian scenario...')
eng = cityflow.Engine(config_path, thread_num=1)
print('Scenario loaded successfully!')
for i in range(10):
    eng.next_step()
print(f'Ran 10 steps. Vehicles: {len(eng.get_vehicles())}')
