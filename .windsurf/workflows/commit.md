---
description: Commit and push changes to GitHub with proper versioning and validation
---

# Commit to GitHub Workflow

Validate, version-check, commit, and push changes.

---

## Step 1: Check what's changed

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && git status --short
```

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && git diff --stat
```

If nothing to commit, report "Working tree clean" and stop.

## Step 2: Run tests

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && python -m pytest tests/ -x -q 2>&1 | Select-Object -Last 10
```

If tests fail (excluding the pre-existing `test_m11_regression` word count failure), **stop and report the failure**. Do not commit broken code.

## Step 3: TypeScript check (if web-ui files changed)

Only run this if `git status` shows changes in `web-ui/`:

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3\web-ui && npx tsc --noEmit --pretty 2>&1 | Select-Object -First 10
```

If TypeScript errors exist, **stop and report**. Do not commit broken code.

## Step 4: Version propagation check

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && python scripts/propagate_version.py
```

If the script reports changes needed, run with `--apply` and include the updated docs in the commit.

## Step 5: Stage and commit

Stage all changes:

```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && git add -A
```

Generate a commit message following conventional commits format:

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation only
- `refactor:` for code restructuring
- `test:` for test changes
- `style:` for formatting/cosmetic changes
- `chore:` for maintenance tasks

For multi-topic commits, use the most significant change as the prefix and list others in the body.

```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && git commit -m "<type>: <short summary>

<optional body with details>"
```

## Step 6: Push to GitHub

```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && git push origin
```

If push fails due to remote changes, pull first:

```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && git pull --rebase origin && git push origin
```

## Step 7: Confirm

Report:
- Branch name
- Commit hash
- Number of files changed
- Test results summary
- Push status

---

## Key Rules

1. **Never commit if tests fail** (except pre-existing `test_m11_regression` word count)
2. **Never commit if TypeScript has errors**
3. **Always check version propagation** before committing doc changes
4. **Use conventional commit messages** with appropriate prefix
5. **Include meaningful commit body** for non-trivial changes (list key files/features)
6. **Push immediately after commit** unless the user says otherwise
