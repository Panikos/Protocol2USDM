/**
 * JSON Patch Application Utilities
 * 
 * Applies RFC 6902 JSON Patch operations to USDM documents.
 */

import { applyPatch, Operation, validate } from 'fast-json-patch';
import type { JsonPatchOp } from './schema';

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
    
    // Deep clone to avoid mutating original
    const cloned = JSON.parse(JSON.stringify(document));
    const ops = toFastJsonPatchOps(patch);
    
    console.log('Applying', ops.length, 'patch operations');
    
    // Apply patch: validateOperation=false (skip to avoid false positives), mutateDocument=true
    applyPatch(cloned, ops, false, true);
    
    // Return the mutated clone
    return { success: true, result: cloned };
  } catch (error) {
    console.error('Patch error:', error);
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
