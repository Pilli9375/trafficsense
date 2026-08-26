import os
import re

print("=== TrafficSense README Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

readme_path = os.path.join(base, 'README.md')
checks['README.md exists'] = os.path.exists(readme_path)

if checks['README.md exists']:
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check sections
    sections = [
        'Abstract',
        'Architecture',
        'Screenshots',
        'Quick Start',
        'Directory Structure',
        'Key Results',
        'Tech Stack',
        'Base Paper',
        'Citation',
        'Timeline',
        'Acknowledgements'
    ]
    
    for section in sections:
        found = section in content
        checks[f'section: {section}'] = found
        print(f"{'[OK]' if found else '[FAIL]'} Section: {section}")
    
    # Check badges
    checks['has_badges'] = 'shields.io' in content
    checks['has_architecture_diagram'] = 'ARCHITECTURE' in content or 'Architecture' in content
    checks['has_code_blocks'] = '```' in content
    checks['has_table'] = '|' in content and '---' in content
    checks['has_citation'] = 'bibtex' in content.lower()
    
    word_count = len(content.split())
    checks['word_count > 500'] = word_count > 500
    print(f"[INFO] README word count: {word_count}")
    
    # Check for placeholder warnings
    if 'screenshots to be captured' in content.lower() or 'placeholder' in content.lower():
        print("[INFO] Screenshots are placeholders — capture before Second Review")

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

total = len(checks)
print(f"\nREADME verification: {passed}/{total} checks passed.")
