import os
import re

print("=== TrafficSense Report Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

# Check files
checks['report.md'] = os.path.exists(os.path.join(base, 'docs', 'report', 'report.md'))
checks['bibliography.bib'] = os.path.exists(os.path.join(base, 'docs', 'report', 'bibliography.bib'))
checks['figures/README.md'] = os.path.exists(os.path.join(base, 'docs', 'report', 'figures', 'README.md'))

# Validate report structure
structure_ok = False
if checks['report.md']:
    with open(os.path.join(base, 'docs', 'report', 'report.md'), 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_sections = [
        'Abstract',
        'Introduction',
        'Literature Review',
        'Methodology',
        'Implementation',
        'Results',
        'Conclusion',
        'References',
        'Appendices'
    ]
    
    for section in required_sections:
        pattern = r'##\s+\d*\.*\s*' + re.escape(section)
        found = bool(re.search(pattern, content, re.IGNORECASE))
        checks[f'section: {section}'] = found
        print(f"{'[OK]' if found else '[FAIL]'} Section: {section}")
    
    # Check word count (rough)
    words = len(content.split())
    print(f"[INFO] Report word count: ~{words}")
    checks['word_count > 3000'] = words > 3000
    
    structure_ok = all(checks.get(f'section: {s}', False) for s in required_sections)

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

total = len(checks)
print(f"\nReport verification: {passed}/{total} checks passed.")
