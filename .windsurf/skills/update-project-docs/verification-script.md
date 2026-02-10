# Verification Script

Run this Python script to check for broken references and version inconsistencies across all docs.

## Full Verification

```python
import re, os, subprocess

ROOT = os.getcwd()
DOCS = ['README.md', 'USER_GUIDE.md', 'QUICK_REFERENCE.md']
errors = 0

# 1. Check test file references
print("=== Test File References ===")
for doc in DOCS:
    path = os.path.join(ROOT, doc)
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    refs = re.findall(r'test_\w+\.py', content)
    for ref in set(refs):
        if not os.path.exists(os.path.join(ROOT, 'tests', ref)) and \
           not os.path.exists(os.path.join(ROOT, 'testing', ref)):
            print(f'  FAIL: {doc} references {ref} which does not exist')
            errors += 1

# 2. Check version consistency
print("\n=== Version Consistency ===")
all_versions = {}
for doc in DOCS + ['CHANGELOG.md']:
    path = os.path.join(ROOT, doc)
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    versions = re.findall(r'(?:\*\*(?:Version|v)\S*\s*\*?\*?\s*)(\d+\.\d+)', content[:500])
    if versions:
        all_versions[doc] = versions[0]
unique = set(all_versions.values())
if len(unique) > 1:
    print(f'  FAIL: Inconsistent versions: {all_versions}')
    errors += 1
else:
    print(f'  OK: All docs at v{unique.pop() if unique else "?"}')

# 3. Check date consistency
print("\n=== Date Consistency ===")
for doc in ['USER_GUIDE.md', 'QUICK_REFERENCE.md']:
    path = os.path.join(ROOT, doc)
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    dates = re.findall(r'Last Updated:\*?\*?\s*(\d{4}-\d{2}-\d{2})', content)
    if len(set(dates)) > 1:
        print(f'  FAIL: {doc} has inconsistent dates: {set(dates)}')
        errors += 1
    elif dates:
        print(f'  OK: {doc} dated {dates[0]}')

# 4. Check CHANGELOG has current version
print("\n=== CHANGELOG Current ===")
changelog = os.path.join(ROOT, 'CHANGELOG.md')
if os.path.exists(changelog):
    with open(changelog, 'r', encoding='utf-8') as f:
        first_entry = f.read(500)
    cl_versions = re.findall(r'## \[(\d+\.\d+\.\d+)\]', first_entry)
    if cl_versions:
        print(f'  Latest CHANGELOG entry: v{cl_versions[0]}')
    else:
        print('  WARN: No version entry found in CHANGELOG top')

# Summary
print(f"\n{'PASS' if errors == 0 else 'FAIL'}: {errors} issue(s) found")
```

## Quick Check (minimal)

```python
import re, os
docs = ['README.md', 'USER_GUIDE.md', 'QUICK_REFERENCE.md']
for doc in docs:
    if not os.path.exists(doc): continue
    with open(doc, 'r', encoding='utf-8') as f:
        content = f.read()
    for ref in set(re.findall(r'test_\w+\.py', content)):
        if not os.path.exists(f'tests/{ref}') and not os.path.exists(f'testing/{ref}'):
            print(f'  WARNING: {doc} references {ref} which does not exist')
print('Done.')
```
