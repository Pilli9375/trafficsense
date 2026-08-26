import os
import subprocess
import sys

print("=" * 70)
print("TRAFFICSENSE — FINAL PACKAGE VERIFICATION")
print("Second Review Readiness Check")
print("=" * 70)

base = r'C:\Pilli\trafficsense'
checks = {}
critical_failures = []

# 1. Check project structure
print("\n[1/7] Project Structure")
required_dirs = ['src', 'docs', 'data', 'models', 'outputs', 'tests']
for d in required_dirs:
    ok = os.path.exists(os.path.join(base, d))
    checks[f'dir_{d}'] = ok
    print(f"  {'[OK]' if ok else '[FAIL]'} {d}/")

# 2. Check source modules
print("\n[2/7] Source Modules")
modules = {
    'perception': ['data_pipeline.py', 'train_yolo.py', 'inference_pipeline.py', 'state_exporter.py'],
    'orchestration': ['perception_adapter.py', 'cooperative_reasoning.py', 'prompt_builder.py'],
    'simulation': ['cityflow_env.py', 'run_trafficsense_sim.py'],
    'dashboard': ['app.py', 'utils.py']
}
for mod, files in modules.items():
    for f in files:
        ok = os.path.exists(os.path.join(base, 'src', mod, f))
        checks[f'src_{mod}_{f}'] = ok
        if not ok:
            critical_failures.append(f'Missing: src/{mod}/{f}')
        print(f"  {'[OK]' if ok else '[FAIL]'} src/{mod}/{f}")

# 3. Check models
print("\n[3/7] Trained Models")
checks['model_best_pt'] = os.path.exists(os.path.join(base, 'models', 'yolo', 'best.pt'))
print(f"  {'[OK]' if checks['model_best_pt'] else '[FAIL]'} models/yolo/best.pt")

# 4. Check outputs
print("\n[4/7] Output Artifacts")
outputs = [
    'yolo_training/results.csv',
    'perception_demo/perception_states.json',
    'simulation_results/fixedtime_metrics.csv',
    'simulation_results/trafficsense_metrics.csv',
    'simulation_results/trafficsense_decisions.json'
]
for out in outputs:
    ok = os.path.exists(os.path.join(base, 'outputs', out))
    checks[f'out_{out.replace("/", "_")}'] = ok
    print(f"  {'[OK]' if ok else '[FAIL]'} outputs/{out}")

# 5. Check documentation
print("\n[5/7] Documentation")
docs = ['report/report.md', 'SECOND_REVIEW_CHECKLIST.md', 'DELIVERY_SUMMARY.md']
for doc in docs:
    ok = os.path.exists(os.path.join(base, 'docs', doc))
    checks[f'doc_{doc}'] = ok
    print(f"  {'[OK]' if ok else '[FAIL]'} docs/{doc}")

# 6. Check README
print("\n[6/7] README")
readme_path = os.path.join(base, 'README.md')
checks['readme'] = os.path.exists(readme_path)
if checks['readme']:
    with open(readme_path, 'r', encoding='utf-8') as f:
        readme = f.read()
    checks['readme_has_badges'] = 'shields.io' in readme
    checks['readme_has_architecture'] = 'ARCHITECTURE' in readme or 'Architecture' in readme
    print(f"  [OK] README.md exists ({len(readme.split())} words)")
    print(f"  {'[OK]' if checks['readme_has_badges'] else '[FAIL]'} Has badges")
    print(f"  {'[OK]' if checks['readme_has_architecture'] else '[FAIL]'} Has architecture diagram")
else:
    critical_failures.append('Missing README.md')

# 7. Check Git
print("\n[7/7] Git Repository")
try:
    result = subprocess.run(['git', 'log', '--oneline'], cwd=base, capture_output=True, text=True)
    commits = result.stdout.strip().split('\n')
    checks['git_commits'] = len(commits) > 10
    print(f"  [OK] {len(commits)} commits")
    
    # Check for uncommitted changes
    status = subprocess.run(['git', 'status', '--porcelain'], cwd=base, capture_output=True, text=True)
    checks['git_clean'] = len(status.stdout.strip()) == 0
    if checks['git_clean']:
        print("  [OK] Working tree clean (all changes committed)")
    else:
        print("  [WARN] Uncommitted changes detected")
        print("  [INFO] Run: git add . && git commit -m '...' && git push")
        
except Exception as e:
    print(f"  [FAIL] Git check error: {e}")
    checks['git_commits'] = False

# Summary
print("\n" + "=" * 70)
passed = sum(1 for v in checks.values() if v)
total = len(checks)
print(f"RESULT: {passed}/{total} checks passed")

if critical_failures:
    print(f"\nCRITICAL FAILURES ({len(critical_failures)}):")
    for cf in critical_failures:
        print(f"  ❌ {cf}")

if passed == total:
    print("\n🎉 ALL CHECKS PASSED!")
    print("🚀 TRAFFICSENSE IS SECOND REVIEW READY!")
    print("\nNext steps:")
    print("  1. Push to GitHub: git push origin master")
    print("  2. Create PPT slides (Step 5.2)")
    print("  3. Record demo video (Step 5.3)")
    print("  4. Prepare for faculty Q&A")
else:
    print(f"\n[WARN] {total - passed} checks failed. Review failures above.")

print("=" * 70)
