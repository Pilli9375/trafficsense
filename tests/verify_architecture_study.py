import os
import sys

print("=== TrafficSense Architecture Study Verification ===")

# WSL vs Windows path resolution for CoLLMLight
base = None
potential_bases = [
    os.path.expanduser("~/trafficsense/CoLLMLight"),
    r'\\wsl.localhost\Ubuntu-22.04\home\pilli\trafficsense\CoLLMLight',
    r'\\wsl$\Ubuntu-22.04\home\pilli\trafficsense\CoLLMLight'
]

for p in potential_bases:
    if os.path.exists(p):
        base = p
        break

if not base:
    base = potential_bases[0] # Fallback for reporting

checks = {
    'CoLLMLight repo exists': os.path.exists(base),
    'run_CoLLMlight.py': os.path.exists(os.path.join(base, 'run_CoLLMlight.py')),
    'run_fts.py': os.path.exists(os.path.join(base, 'run_fts.py')),
    'ppo_ft.py': os.path.exists(os.path.join(base, 'ppo_ft.py')),
    'config/ directory': os.path.exists(os.path.join(base, 'config')),
    'utils/ directory': os.path.exists(os.path.join(base, 'utils')),
    'data/ directory': os.path.exists(os.path.join(base, 'data')),
}

# Check for key files found during grep
key_files = []
if os.path.exists(base):
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.endswith('.py'):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, base)
                key_files.append(rel)

print(f"\n[INFO] Found {len(key_files)} Python files")

# Check docs were created
# Adjust base path for Windows script execution logic
docs_base = r'C:\Pilli\trafficsense\docs' if os.name == 'nt' else os.path.expanduser('~/trafficsense/docs')
# If run inside WSL, docs_base might not exist because docs are on C:\
if not os.path.exists(docs_base) and not os.name == 'nt':
    docs_base = '/mnt/c/Pilli/trafficsense/docs'

doc_checks = {
    'COLLMLIGHT_ARCHITECTURE.md': os.path.exists(os.path.join(docs_base, 'COLLMLIGHT_ARCHITECTURE.md')),
    'INTEGRATION_POINTS.md': os.path.exists(os.path.join(docs_base, 'INTEGRATION_POINTS.md')),
}

passed = 0
for name, ok in {**checks, **doc_checks}.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

print(f"\nArchitecture study verification: {passed}/{len(checks) + len(doc_checks)} checks passed.")
