import cityflow
eng = cityflow.Engine('/mnt/c/Pilli/trafficsense/data/synthetic/indian_2x2_config.json', thread_num=1)
for _ in range(10):
    eng.next_step()
print('OK')
