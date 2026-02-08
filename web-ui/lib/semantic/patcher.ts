/**
 * JSON Patch Application Utilities
 * 
 * Applies RFC 6902 JSON Patch operations to USDM documents.
 */

import { applyPatch, Operation, validate } from 'fast-json-patch';
import type { JsonPatchOp } from './schema';
import { isImmutablePath } from './schema';

/** RFC 6902 path must start with / */
const VALID_PATH_RE = /^\/[\w\[\]\-\.~\/]*$/;

/**
 * Validate structural correctness of patch operations beyond immutable-path checks.
 * Catches malformed paths, missing values, and invalid op types before application.
 */
export function validatePatchOps(patch: JsonPatchOp[]): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  for (let i = 0; i < patch.length; i++) {
    const op = patch[i];
    const prefix = `Op[${i}] (${op.op})`;

    // Path must start with /
    if (!op.path || !op.path.startsWith('/')) {
      errors.push(`${prefix}: path must start with / (got "${op.path}")`);
    }

    // Immutable path check
    if (isImmutablePath(op.path)) {
      errors.push(`${prefix}: targets immutable path ${op.path}`);
    }

    // add/replace require a value
    if ((op.op === 'add' || op.op === 'replace') && op.value === undefined) {
      errors.push(`${prefix}: missing required 'value'`);
    }

    // move/copy require a from
    if ((op.op === 'move' || op.op === 'copy') && !('from' in op && op.from)) {
      errors.push(`${prefix}: missing required 'from'`);
    }
  }
  return { valid: errors.length === 0, errors };
}

/**
 * Convert our schema's patch ops to fast-json-patch format
 */
function toFastJsonPatchOps(patch: JsonPatchOp[]): Operation[] {
  return patch.map(op => {
    switch (op.op) {
      case 'add':
        return { op: 'add', path: op.path, value: op.value };
      case 'remove':
        return { op: 'remove', path: op.path };
      case 'replace':
        return { op: 'replace', path: op.path, value: op.value };
      case 'move':
        return { op: 'move', path: op.path, from: op.from };
      case 'copy':
        return { op: 'copy', path: op.path, from: op.from };
      case 'test':
        return { op: 'test', path: op.path, value: op.value };
      default:
        throw new Error(`Unknown operation type`);
    }
  });
}

/**
 * Validate a JSON Patch against a document without applying it
 */
export function validatePatch(
  document: unknown,
  patch: JsonPatchOp[]
): { valid: boolean; errors: string[] } {
  try {
    const ops = toFastJsonPatchOps(patch);
    const errors = validate(ops, document as object);
    
    if (errors) {
      return {
        valid: false,
        errors: [errors.message || 'Patch validation failed'],
      };
    }
    
    return { valid: true, errors: [] };
  } catch (error) {
    return {
      valid: false,
      errors: [error instanceof Error ? error.message : 'Unknown validation error'],
    };
  }
}

/**
 * Apply a JSON Patch to a document
 * 
 * Returns the patched document or throws on error.
 */
export function applySemanticPatch(
  document: unknown,
  patch: JsonPatchOp[]
): { success: true; result: unknown } | { success: false; error: string } {
  try {
    // Handle empty patch
    if (!patch || patch.length === 0) {
      return { success: true, result: document };
    }

    // Structural validation before applying
    const structCheck = validatePatchOps(patch);
    if (!structCheck.valid) {
      return { success: false, error: structCheck.errors.join('; ') };
    }
    
    // Deep clone to avoid mutating original
    const cloned = JSON.parse(JSON.stringify(document));
    const ops = toFastJsonPatchOps(patch);
    
    // Apply patch: validateOperation=false (skip to avoid false positives), mutateDocument=true
    applyPatch(cloned, ops, false, true);
    
    // Return the mutated clone
    return { success: true, result: cloned };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown patch error',
    };
  }
}

/**
 * Dry-run a patch to check if it would succeed
 */
export function dryRunPatch(
  document: unknown,
  patch: JsonPatchOp[]
): { wouldSucceed: boolean; error?: string } {
  const result = applySemanticPatch(document, patch);
  if (result.success) {
    return { wouldSucceed: true };
  }
  return { wouldSucceed: false, error: result.error };
}
