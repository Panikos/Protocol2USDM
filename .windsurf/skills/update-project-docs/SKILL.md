---
name: update-project-docs
description: Check and update all project documentation (README, USER_GUIDE, CHANGELOG, QUICK_REFERENCE, ARCHITECTURE, ROADMAP, FULL_PROJECT_REVIEW) to reflect recent code changes. Gathers live context from git and pytest, identifies stale sections, makes targeted edits, verifies references, and stages for commit.
---

# Update Project Documentation Skill

This skill provides comprehensive knowledge for keeping all Protocol2USDM documentation in sync with the codebase. It should be invoked before or after significant commits, or on demand when the user asks to update docs.

## When to Use

- After completing a feature, enhancement, or bug fix
- Before creating a release or merging a branch
- When the user says "update docs", "sync documentation", or similar
- After any commit that adds new files, modules, tests, or CLI flags

## Process

### Phase 1: Gather Context

1. Run `git log --oneline -10` to see recent commits
2. Run `git diff --stat HEAD~3` to see what files changed
3. Run `git status --short` for uncommitted changes
4. Run `python -m pytest tests/ --co -q` to get live test count
5. Read the first 10-15 lines of each doc file to check current version strings

### Phase 2: Identify Staleness

Compare the git log against each doc's current state. Use the doc inventory (see `doc-inventory.md`) to know which sections in each file need checking.

Categorize changes:

| Change Type | Docs to Update |
|-------------|---------------|
| New modules/files | README (Project Structure), ARCHITECTURE |
| New features | README (What's New), USER_GUIDE (What's New banner), CHANGELOG |
| New/changed tests | README (Testing), QUICK_REFERENCE (Testing) |
| Bug fixes | CHANGELOG |
| Architecture changes | ARCHITECTURE |
| New CLI flags | QUICK_REFERENCE, USER_GUIDE |
| Version bump | All docs — version strings must be consistent |
| Enhancement completed | FULL_PROJECT_REVIEW, README (Roadmap) |

If nothing significant changed since the last doc update, report "Docs are up to date" and stop.

### Phase 3: Make Edits

Follow the update rules in `update-rules.md` for each document. Key principles:

1. **Never fabricate test counts or coverage** — always use live numbers from pytest
2. **Test commands must reference files that actually exist** in `tests/` or `testing/`
3. **Version strings must be consistent** across all docs
4. **Dates use ISO-8601** format (YYYY-MM-DD)
5. **CHANGELOG entries grouped by feature**, not by file
6. **Project Structure in README must match reality** — verify with find_by_name if unsure
7. **Previous releases in README go into `<details>` blocks**
8. **Enhancement IDs** (E7, P12, etc.) should be referenced in CHANGELOG and FULL_PROJECT_REVIEW

### Phase 4: Verify

Run the reference check script to catch broken test file references and version inconsistencies:

```python
import re, os
docs = ['README.md', 'USER_GUIDE.md', 'QUICK_REFERENCE.md']
errors = 0
for doc in docs:
    if not os.path.exists(doc): continue
    with open(doc, 'r', encoding='utf-8') as f:
        content = f.read()
    refs = re.findall(r'test_\w+\.py', content)
    for ref in set(refs):
        if not os.path.exists(f'tests/{ref}') and not os.path.exists(f'testing/{ref}'):
            print(f'  WARNING: {doc} references {ref} which does not exist')
            errors += 1
    versions = re.findall(r'\*\*(?:Version|v)(?:ersion)?[:\s]*\*?\*?\s*(\d+\.\d+)', content)
    if versions and len(set(versions)) > 1:
        print(f'  WARNING: {doc} has inconsistent versions: {set(versions)}')
        errors += 1
if errors == 0:
    print('All references and versions OK.')
else:
    print(f'{errors} issue(s) found — fix before committing.')
```

### Phase 5: Stage and Summarize

Show the user a summary of what was updated, stage the files, and ask if they want to commit now or include in a larger commit.
