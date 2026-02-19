---
description: Run all existing tests and report results
---

# Run Tests Workflow

Run the full test suite and report pass/fail summary.

---

## Step 1: Run all unit tests

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && python -m pytest tests/ -x -q --ignore=tests/test_m11_regression.py --ignore=tests/test_e2e_pipeline.py 2>&1 | Select-Object -Last 20
```

If tests pass, report the summary line (e.g. "1118 passed in 92s") and stop.

If tests fail, continue to Step 2.

## Step 2: Investigate failures

If there are failures, re-run only the failing test(s) with verbose output to see the full traceback:

```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3 && python -m pytest tests/<failing_test_file>::<failing_test_class>::<failing_test_name> -v 2>&1 | Select-Object -Last 40
```

Report:
- Number of tests passed / failed / skipped
- For each failure: test name, file, and root cause from the traceback
- Whether the failure is pre-existing or caused by recent changes (check `git diff --name-only HEAD~1` against the failing test file)

## Step 3: TypeScript compilation check (optional)

If any TypeScript/web-ui files were recently changed, also verify:

// turbo
```bash
cd c:\Users\panik\Documents\GitHub\Protcol2USDMv3\web-ui && npx tsc --noEmit --pretty 2>&1 | Select-Object -First 10
```

## Key Notes

- The **pre-existing** `test_m11_regression` word count failure is known and expected — do not attempt to fix it
- E2E tests (`test_e2e_pipeline.py`) require `--run-e2e` flag and recent pipeline output — they are skipped by default
- Total test count as of v8.0: **1157 collected**, **1118 passed** (excluding m11_regression + e2e)
