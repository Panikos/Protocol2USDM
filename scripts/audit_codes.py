"""Extract all C-codes from active Python files and batch-verify against EVS."""
import re
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

codes = set()
for root, dirs, files in os.walk('.'):
    # Skip archive, git, node_modules, web-ui
    skip = False
    for s in ['archive', '.git', 'node_modules', 'web-ui', '__pycache__', 'tools']:
        if s in root:
            skip = True
            break
    if skip:
        continue
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            for m in re.findall(r'"(C\d{4,6})"', content):
                codes.add(m)

# Also check tests
for root, dirs, files in os.walk('./tests'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            for m in re.findall(r'"(C\d{4,6})"', content):
                codes.add(m)

print(f"Found {len(codes)} unique C-codes in active codebase")

if "--verify" in sys.argv:
    from core.evs_client import EVSClient
    client = EVSClient()
    for code in sorted(codes):
        result = client.fetch_ncit_code(code)
        if result:
            decode = result.get("decode", "???")
            print(f"  {code}: {decode}")
        else:
            print(f"  {code}: NOT FOUND IN EVS")
else:
    for code in sorted(codes):
        print(f"  {code}")
