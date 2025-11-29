# CDISC CORE Engine Bug Report

**Date:** 2025-11-29  
**CORE Version:** 0.13.0  
**Platform:** Windows 11 (64-bit)  
**Standard:** USDM 4.0  

---

## Summary

Two USDM 4.0 conformance rules (`CORE-000955` and `CORE-000956`) crash with a `TypeError` when processing valid USDM JSON data. The error occurs in the JSONata processor and causes the entire validation to fail.

---

## Error Details

### Stack Trace

```
multiprocessing.pool.RemoteTraceback: 
"""
Traceback (most recent call last):
  File "cdisc_rules_engine\utilities\jsonata_processor.py", line 42, in execute_jsonata_rule
  File "jsonata\jsonata.py", line 1978, in evaluate
  File "jsonata\jsonata.py", line 1969, in evaluate
  File "jsonata\jsonata.py", line 234, in eval
  File "jsonata\jsonata.py", line 272, in _eval
  File "jsonata\jsonata.py", line 1097, in evaluate_block
  File "jsonata\jsonata.py", line 234, in eval
  File "jsonata\jsonata.py", line 286, in _eval
  File "jsonata\jsonata.py", line 1275, in evaluate_apply_expression
  File "jsonata\jsonata.py", line 234, in eval
  File "jsonata\jsonata.py", line 286, in _eval
  File "jsonata\jsonata.py", line 1275, in evaluate_apply_expression
  File "jsonata\jsonata.py", line 234, in eval
  File "jsonata\jsonata.py", line 252, in _eval
  File "jsonata\jsonata.py", line 375, in evaluate_path
  File "jsonata\jsonata.py", line 951, in evaluate_group_expression
TypeError: 'NoneType' object is not subscriptable

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "cdisc_rules_engine\rules_engine.py", line 195, in validate_single_dataset
  File "cdisc_rules_engine\rules_engine.py", line 339, in validate_rule
  File "cdisc_rules_engine\utilities\jsonata_processor.py", line 44, in execute_jsonata_rule
cdisc_rules_engine.exceptions.custom_exceptions.RuleExecutionError: 
  Error evaluating JSONata Rule with Core Id: CORE-000956
  TypeError: 'NoneType' object is not subscriptable

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "multiprocessing\pool.py", line 125, in worker
  File "scripts\run_validation.py", line 98, in validate_single_rule
  File "cdisc_rules_engine\rules_engine.py", line 116, in validate_single_rule
  File "cdisc_rules_engine\rules_engine.py", line 235, in validate_single_dataset
  File "cdisc_rules_engine\rules_engine.py", line 539, in handle_validation_exceptions
  File "<frozen ntpath>", line 270, in basename
  File "<frozen ntpath>", line 241, in split
TypeError: expected str, bytes or os.PathLike object, not NoneType
"""
```

### Secondary Bug in Error Handler

When the JSONata rule fails, the error handler at `rules_engine.py:539` calls `ntpath.basename()` with a `None` value, causing a second `TypeError`. This masks the original error and causes the validation to crash rather than gracefully skip the failed rule.

---

## Affected Rules

### CORE-000955

| Property | Value |
|----------|-------|
| **Core ID** | CORE-000955 |
| **Rule Identifier** | DDF00173 |
| **Description** | Every identifier must be unique within the scope of an identified organization. |
| **Entities** | StudyIdentifier, ReferenceIdentifier, AdministrableProductIdentifier, MedicalDeviceIdentifier |
| **Status** | Published |

**JSONata Condition:**
```jsonata
study.versions@$sv.
  ($sv.**.*[scopeId and text and instanceType])@$i.
    ($sv.organizations[id=$i.scopeId])@$o.
      {
        "group": $join([$i.text,$i.scopeId,$i.instanceType],"|"),
        "details": $
          {
            "instanceType": $i.instanceType,
            "id": $i.id,
            "path": $i._path,
            "text": $i.text,
            "scopeId": $i.scopeId,
            "Organization.name": $o.name,
            "type.decode": $i.type.decode
          }
      }{group: $count(details)>1?$.details}
      ~> $each(function($v){$v}) ~> $reduce($append)
```

---

### CORE-000956

| Property | Value |
|----------|-------|
| **Core ID** | CORE-000956 |
| **Rule Identifier** | DDF00174 |
| **Description** | An identified organization is not expected to have more than 1 identifier for the study. |
| **Entities** | StudyIdentifier |
| **Status** | Published |

**JSONata Condition:**
```jsonata
study.versions@$sv.
  ($sv.studyIdentifiers)@$i.
  ($sv.organizations[id=$i.scopeId])@$o.
    {
      "group": $join([$i.scopeId,$i.instanceType],"|"),
      "details": $
        {
          "instanceType": $i.instanceType,
          "id": $i.id,
          "path": $i._path,
          "text": $i.text,
          "scopeId": $i.scopeId,
          "Organization.name": $o.name
        }
      }{group: $count(details)>1?$.details}
      ~> $each(function($v){$v}) ~> $reduce($append)
```

---

## Root Cause Analysis

The JSONata expressions in both rules use a pattern like:

```jsonata
($sv.organizations[id=$i.scopeId])@$o
```

This filters organizations where `id` equals `scopeId`. When `scopeId` is `null` or when there are no matching organizations, the downstream grouping expression:

```jsonata
{group: $count(details)>1?$.details}
```

fails with `TypeError: 'NoneType' object is not subscriptable` because the grouping operation receives `None` instead of an array/object.

---

## Reproduction Steps

1. Create a valid USDM 4.0 JSON file with:
   - `StudyIdentifier` entities where `scopeId` may be null or reference a missing organization
   - Or organizations without matching identifiers

2. Run CORE validation:
   ```bash
   core.exe validate -s usdm -v 4-0 -dp <path_to_usdm.json> -o output.json -of JSON
   ```

3. Observe the crash at ~82-97% progress

---

## Workaround

Exclude the affected rules using the `-er` flag:

```bash
core.exe validate -s usdm -v 4-0 -dp <path_to_usdm.json> -o output.json -of JSON -er CORE-000955 -er CORE-000956
```

With these rules excluded, validation completes successfully with 0 issues.

---

## Suggested Fixes

### 1. JSONata Null Handling

Update the JSONata expressions to handle null/empty results gracefully:

```jsonata
($sv.organizations[id=$i.scopeId])@$o ? ... : []
```

Or use `$exists()` / `$count()` guards before grouping operations.

### 2. Error Handler Path Fix

In `rules_engine.py:539`, the `handle_validation_exceptions` function should check for `None` before calling `os.path.basename()`:

```python
# Before
path = os.path.basename(dataset_path)

# After  
path = os.path.basename(dataset_path) if dataset_path else "unknown"
```

### 3. Graceful Rule Failure

Consider allowing individual rules to fail gracefully without crashing the entire validation process. Failed rules could be logged and reported separately.

---

## Environment

- **CORE Version:** 0.13.0
- **OS:** Windows 11 (64-bit)
- **Python:** Embedded in core.exe
- **Data:** USDM 4.0 compliant JSON (validated by official `usdm` Python package v0.64.0)

---

## Contact

Report submitted by Protocol2USDM project.  
GitHub: https://github.com/Panikos/Protcol2USDMv3
