import cityflow
config_path = '/mnt/c/Pilli/trafficsense/data/synthetic/indian_2x2_config.json'
print('Loading Indian scenario...')
eng = cityflow.Engine(config_path, thread_num=1)
print('Scenario loaded!')
for i in range(100):
    eng.next_step()
    if (i + 1) % 10 == 0:
        vehs = eng.get_vehicles()
        print(f'Step {i+1}: {len(vehs)} vehicles')
print(f'FINAL: {len(eng.get_vehicles())} vehicles after 100 steps')
