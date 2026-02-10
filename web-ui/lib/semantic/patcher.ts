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

/** Matches an ID-based path segment like @id:some-uuid-here */
const ID_SEGMENT_RE = /^@id:(.+)$/;

/**
 * Resolve ID-based path segments (@id:xxx) to array indices.
 * 
 * Walks the document tree following the path. When a segment matches
 * `@id:<value>`, the parent must be an array; we find the element whose
 * `.id` property equals `<value>` and replace the segment with its index.
 * 
 * Returns the resolved RFC 6902 path string, or throws if an ID cannot
 * be found.
 */
export function resolveIdPath(document: unknown, path: string): string {
  if (!path.includes('@id:')) return path;

  const segments = path.split('/').filter(Boolean);
  const resolved: string[] = [];
  let cursor: unknown = document;

  for (const seg of segments) {
    const idMatch = seg.match(ID_SEGMENT_RE);
    if (idMatch) {
      const targetId = idMatch[1];
      if (!Array.isArray(cursor)) {
        throw new Error(
          `@id:${targetId} used on non-array at /${resolved.join('/')}`
        );
      }
      const idx = (cursor as Array<{ id?: string }>).findIndex(
        (item) => item?.id === targetId
      );
      if (idx === -1) {
        throw new Error(
          `Entity with id "${targetId}" not found in array at /${resolved.join('/')}`
        );
      }
      resolved.push(String(idx));
      cursor = cursor[idx];
    } else {
      resolved.push(seg);
      if (cursor !== null && cursor !== undefined && typeof cursor === 'object') {
        if (Array.isArray(cursor)) {
          const numIdx = seg === '-' ? -1 : Number(seg);
          cursor = numIdx >= 0 ? cursor[numIdx] : undefined;
        } else {
          cursor = (cursor as Record<string, unknown>)[seg];
        }
      } else {
        cursor = undefined;
      }
    }
  }

  return '/' + resolved.join('/');
}

/**
 * Resolve all ID-based paths in a patch operation.
 * Returns a new op with resolved paths (does not mutate the original).
 */
function resolveOpPaths(document: unknown, op: JsonPatchOp): JsonPatchOp {
  const resolved = { ...op, path: resolveIdPath(document, op.path) };
  if ('from' in op && op.from) {
    (resolved as { from: string }).from = resolveIdPath(document, op.from);
  }
  return resolved;
}

/**
 * Resolve all ID-based paths in a patch array.
 * Each op is resolved against the document *after* applying all preceding ops,
 * so that newly-added entities can be referenced by subsequent ops.
 */
export function resolveAllIdPaths(
  document: unknown,
  patch: JsonPatchOp[]
): { resolved: JsonPatchOp[]; errors: string[] } {
  const resolved: JsonPatchOp[] = [];
  const errors: string[] = [];
  // Work on a mutable clone so sequential resolution sees prior mutations
  let doc = JSON.parse(JSON.stringify(document));

  for (let i = 0; i < patch.length; i++) {
    try {
      const op = resolveOpPaths(doc, patch[i]);
      resolved.push(op);
      // Apply this op to keep doc in sync for subsequent resolutions
      const fastOps = toFastJsonPatchOps([op]);
      applyPatch(doc, fastOps, false, true);
    } catch (err) {
      errors.push(`Op[${i}]: ${err instanceof Error ? err.message : String(err)}`);
      // Still push original op so indices stay aligned for error reporting
      resolved.push(patch[i]);
    }
  }

  return { resolved, errors };
}

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

    // Immutable path check (resolve @id: segments for immutable check)
    const checkPath = op.path.replace(/@id:[^/]+/g, '0');
    if (isImmutablePath(checkPath)) {
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
    
    // Resolve ID-based paths (@id:xxx → array indices)
    const hasIdPaths = patch.some(op => op.path.includes('@id:') || ('from' in op && (op as { from?: string }).from?.includes('@id:')));
    let resolvedPatch = patch;
    if (hasIdPaths) {
      const resolution = resolveAllIdPaths(cloned, patch);
      if (resolution.errors.length > 0) {
        return { success: false, error: `ID path resolution failed: ${resolution.errors.join('; ')}` };
      }
      resolvedPatch = resolution.resolved;
    }
    
    // Re-clone since resolveAllIdPaths may have mutated the first clone
    const target = hasIdPaths ? JSON.parse(JSON.stringify(document)) : cloned;
    const ops = toFastJsonPatchOps(resolvedPatch);
    
    // Apply patch: validateOperation=false (skip to avoid false positives), mutateDocument=true
    applyPatch(target, ops, false, true);
    
    // Return the mutated clone
    return { success: true, result: target };
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
