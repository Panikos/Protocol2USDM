---
description: Automatically check and update all project documentation (README, USER_GUIDE, CHANGELOG, QUICK_REFERENCE, ARCHITECTURE, ROADMAP) to reflect recent code changes. Invoke before committing or on demand.
---

# Update Documentation Workflow

When invoked, automatically gather context, identify stale docs, make edits, verify, and optionally commit.

---

## Step 1: Gather context — what changed recently

Run these commands to understand the current state:

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && git log --oneline -10
```

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && git diff --stat HEAD~3
```

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && git status --short
```

// turbo
Read the canonical version (single source of truth):
```bash
python -c "from core.constants import VERSION; print(f'VERSION={VERSION}')"
```

Then read the current state of all doc files:

Read these files (batch):
- `core/constants.py` (VERSION is the single source of truth for all docs)
- `README.md` (first 10 lines for version)
- `USER_GUIDE.md` (first 10 lines for version)
- `QUICK_REFERENCE.md` (first 10 lines for version)
- `CHANGELOG.md` (first 15 lines for latest entry)
- `docs/ROADMAP.md` (full)
- `docs/FULL_PROJECT_REVIEW.md` (grep for enhancement status)

## Step 2: Get live test count and coverage

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && python -m pytest tests/ --co -q 2>&1 | Select-Object -Last 3
```

## Step 3: Categorize changes and decide what to update

Based on the git log and diff, categorize:

| Change Type | Docs to Update |
|-------------|---------------|
| **New modules/files** | README.md (Project Structure), ARCHITECTURE.md |
| **New features** | README.md (What's New), USER_GUIDE.md (What's New banner), CHANGELOG.md |
| **New/changed tests** | README.md (Testing section), QUICK_REFERENCE.md (Testing section) |
| **Bug fixes** | CHANGELOG.md |
| **Architecture changes** | docs/ARCHITECTURE.md |
| **New CLI flags** | QUICK_REFERENCE.md, USER_GUIDE.md |
| **Version bump** | All docs — version strings must be consistent |
| **Enhancement completed** | docs/FULL_PROJECT_REVIEW.md, README.md (Roadmap) |

If nothing significant changed since the last doc update, report "Docs are up to date" and stop.

## Step 4: Update each stale doc

**IMPORTANT: The version in `core/constants.py` → `VERSION` is the single source of truth.** All doc version references (README, USER_GUIDE, QUICK_REFERENCE, CHANGELOG, FULL_PROJECT_REVIEW) must match this value. When bumping the version, update `constants.py` FIRST, then propagate to all docs.

The version format is `MAJOR.MINOR.PATCH` (e.g. `7.17.0`). Docs use shortened `MAJOR.MINOR` (e.g. `v7.17`). The CHANGELOG uses the full semver `[7.17.0]`.

### CHANGELOG.md
- Add new version entry at top (after `---` separator) if not already present
- Format: `## [X.Y.Z] – YYYY-MM-DD` with ISO-8601 date — version MUST match `constants.py`
- Group by feature area, include tables for new files
- Reference enhancement IDs (E7, P12, etc.) when applicable

### README.md
- **What's New in vX.Y** — Add new features; collapse older releases into `<details>` blocks
- **Project Structure** — Must match actual directory layout (check with `find_by_name`)
- **Testing** — Update test count (from Step 2), coverage %, test commands (must reference real files)
- **Roadmap / TODO** — Move completed items to `[x]`, add new planned items

### USER_GUIDE.md
- **Version** at top (`**Version:** X.Y`) and **Last Updated** at top and bottom
- **What's New** banner — one-line summary of latest version
- **Testing section** — pytest commands must reference actual test files
- **Output Directory Structure** — Add new output files if any

### QUICK_REFERENCE.md
- **Version** at top and **Last Updated** at bottom
- **Output Files** tree — Add new output files
- **Testing** commands — Must reference actual test files
- **Key Files** table — Add new important files

### docs/ARCHITECTURE.md (only if architecture changed)
- New modules or packages
- Pipeline flow changes
- New rendering/validation paths

### docs/FULL_PROJECT_REVIEW.md
- Mark completed enhancements as ✅ FIXED
- Update status of in-progress items

### docs/ROADMAP.md
- Move completed items to "Completed Features" section
- Add new planned items

## Step 5: Verify no broken references

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && python -c "
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
    # Check version consistency
    versions = re.findall(r'\*\*(?:Version|v)(?:ersion)?[:\s]*\*?\*?\s*(\d+\.\d+)', content)
    if versions and len(set(versions)) > 1:
        print(f'  WARNING: {doc} has inconsistent versions: {set(versions)}')
        errors += 1
# Cross-check docs against constants.py
from core.constants import VERSION
canonical = '.'.join(VERSION.split('.')[:2])  # e.g. '7.17'
for doc in docs:
    if not os.path.exists(doc): continue
    with open(doc, 'r', encoding='utf-8') as f:
        content = f.read()
    doc_versions = re.findall(r'\*\*(?:Version|v)[:\s]*\*?\*?\s*(\d+\.\d+)', content)
    for v in set(doc_versions):
        if v != canonical:
            print(f'  WARNING: {doc} has version {v} but constants.py says {canonical}')
            errors += 1
if errors == 0:
    print(f'All references and versions OK (canonical: v{canonical}).')
else:
    print(f'{errors} issue(s) found — fix before committing.')
"
```

## Step 6: Show summary and stage

Show the user a summary of what was updated, then stage the doc files:

```bash
git add README.md USER_GUIDE.md CHANGELOG.md QUICK_REFERENCE.md docs/ARCHITECTURE.md docs/ROADMAP.md docs/FULL_PROJECT_REVIEW.md
```

Ask the user if they want to commit the doc updates now or include them in a larger commit.

---

## Key Rules

1. **Never fabricate test counts or coverage** — always get live numbers from pytest
2. **Test commands must reference files that actually exist** in `tests/` or `testing/`
3. **Version strings must be consistent** across all docs
4. **Dates use ISO-8601** format (YYYY-MM-DD)
5. **CHANGELOG entries are grouped by feature**, not by file
6. **Don't update docs if nothing changed** — report "up to date" and stop
7. **Project Structure in README must match reality** — verify with `find_by_name` if unsure
8. **Previous releases in README go into `<details>` blocks** to keep What's New focused
9. **Enhancement IDs** (E7, P12, etc.) should be referenced in CHANGELOG and FULL_PROJECT_REVIEW
10. **Always run the reference check** (Step 5) before committing
11. **`core/constants.py` → `VERSION` is the single source of truth** — all doc version strings derive from it. Bump it FIRST, then propagate. Never hardcode versions in docs without checking constants.py.
