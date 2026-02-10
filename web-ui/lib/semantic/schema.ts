/**
 * Semantic Draft Schema
 * 
 * Defines the structure for semantic editing drafts using JSON Patch (RFC 6902).
 */

import { z } from 'zod';

/**
 * JSON Patch operation schema (RFC 6902)
 */
export const JsonPatchOpSchema = z.discriminatedUnion('op', [
  z.object({
    op: z.literal('add'),
    path: z.string(),
    value: z.unknown(),
  }),
  z.object({
    op: z.literal('remove'),
    path: z.string(),
  }),
  z.object({
    op: z.literal('replace'),
    path: z.string(),
    value: z.unknown(),
  }),
  z.object({
    op: z.literal('move'),
    from: z.string(),
    path: z.string(),
  }),
  z.object({
    op: z.literal('copy'),
    from: z.string(),
    path: z.string(),
  }),
  z.object({
    op: z.literal('test'),
    path: z.string(),
    value: z.unknown(),
  }),
]);

export type JsonPatchOp = z.infer<typeof JsonPatchOpSchema>;

/**
 * Semantic draft document schema
 */
export const SemanticDraftSchema = z.object({
  version: z.number().default(1),
  protocolId: z.string(),
  usdmRevision: z.string(),
  status: z.enum(['draft', 'published']),
  createdAt: z.string().datetime().optional(),
  updatedAt: z.string().datetime(),
  updatedBy: z.string(),
  patch: z.array(JsonPatchOpSchema),
});

export type SemanticDraft = z.infer<typeof SemanticDraftSchema>;

/**
 * Request body for PUT /api/protocols/[id]/semantic/draft
 */
export const SaveDraftRequestSchema = z.object({
  protocolId: z.string(),
  usdmRevision: z.string(),
  updatedBy: z.string(),
  patch: z.array(JsonPatchOpSchema),
});

export type SaveDraftRequest = z.infer<typeof SaveDraftRequestSchema>;

/**
 * Immutable USDM paths that cannot be edited
 */
export const IMMUTABLE_PATHS = [
  '/study/id',
  '/study/versions/0/id',
  '/usdmVersion',
  '/generatedAt',
  '/_provenance',
];

/**
 * Check if a path targets an immutable field
 */
export function isImmutablePath(path: string): boolean {
  return IMMUTABLE_PATHS.some(immutable => 
    path === immutable || path.startsWith(immutable + '/')
  );
}

/**
 * Validate that no patch operations target immutable fields
 */
export function validatePatchPaths(patch: JsonPatchOp[]): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  
  for (const op of patch) {
    if (isImmutablePath(op.path)) {
      errors.push(`Cannot modify immutable path: ${op.path}`);
    }
    if ('from' in op && isImmutablePath(op.from)) {
      errors.push(`Cannot move/copy from immutable path: ${op.from}`);
    }
  }
  
  return { valid: errors.length === 0, errors };
}

/**
 * Create an empty semantic draft
 */
export function createEmptySemanticDraft(
  protocolId: string,
  usdmRevision: string,
  updatedBy: string
): SemanticDraft {
  const now = new Date().toISOString();
  return {
    version: 1,
    protocolId,
    usdmRevision,
    status: 'draft',
    createdAt: now,
    updatedAt: now,
    updatedBy,
    patch: [],
  };
}

/**
 * Validation result structure
 */
export const ValidationResultSchema = z.object({
  valid: z.boolean(),
  errors: z.number(),
  warnings: z.number(),
  details: z.array(z.object({
    severity: z.enum(['error', 'warning', 'info']),
    message: z.string(),
    path: z.string().optional(),
  })).optional(),
});

export type ValidationResult = z.infer<typeof ValidationResultSchema>;

/**
 * Publish response structure
 */
export const PublishResponseSchema = z.object({
  success: z.boolean(),
  publishedAt: z.string().datetime().optional(),
  publishedFile: z.string().optional(),
  validation: z.object({
    schema: ValidationResultSchema,
    usdm: ValidationResultSchema,
    core: z.object({
      success: z.boolean(),
      issues: z.number(),
      warnings: z.number(),
    }),
  }).optional(),
  error: z.string().optional(),
});

export type PublishResponse = z.infer<typeof PublishResponseSchema>;

// ── Audit Trail (P3) ─────────────────────────────────────────────

/**
 * A single entry in the protocol change log.
 * Forms a SHA-256 hash chain: each entry's `hash` covers its own content
 * plus the previous entry's hash, creating a tamper-evident chain.
 */
export interface ChangeLogEntry {
  /** Sequential version number (1-based) */
  version: number;
  /** ISO 8601 timestamp */
  publishedAt: string;
  /** User who published */
  publishedBy: string;
  /** Reason for change (required on publish) */
  reason: string;
  /** Number of JSON Patch operations applied */
  patchCount: number;
  /** Summary of changed paths (first N) */
  changedPaths: string[];
  /** SHA-256 of the published USDM JSON */
  usdmHash: string;
  /** SHA-256 of the previous entry's hash (empty string for first entry) */
  previousHash: string;
  /** SHA-256 hash of this entry (covers all fields above + previousHash) */
  hash: string;
  /** Validation result summary */
  validation?: {
    schemaValid: boolean;
    usdmValid: boolean;
    errorCount: number;
    warningCount: number;
    forcedPublish: boolean;
  };
}

/**
 * The full change log for a protocol.
 */
export interface ChangeLog {
  protocolId: string;
  entries: ChangeLogEntry[];
}

// ── ID-based Path Helpers ──────────────────────────────────────────

/** Common USDM base paths */
const SD = '/study/versions/0/studyDesigns/0';
const SV = '/study/versions/0';

/**
 * Build an ID-based JSON Patch path for a USDM entity property.
 * 
 * Instead of fragile array-index paths like:
 *   `/study/versions/0/studyDesigns/0/objectives/3/text`
 * 
 * This produces stable ID-based paths like:
 *   `/study/versions/0/studyDesigns/0/objectives/@id:obj-uuid/text`
 * 
 * The `@id:` segments are resolved to indices at patch-application time
 * by `resolveIdPath()` in patcher.ts.
 */
export function idPath(
  collection: string,
  entityId: string,
  property?: string,
  options?: { nested?: { collection: string; entityId: string; property?: string } }
): string {
  // Determine base path based on collection location in USDM hierarchy
  const versionLevelCollections = new Set([
    'eligibilityCriterionItems', 'narrativeContentItems', 'abbreviations',
    'studyInterventions', 'administrableProducts', 'titles',
    'studyIdentifiers', 'amendments', 'conditions', 'medicalDevices',
  ]);

  const base = versionLevelCollections.has(collection) ? SV : SD;
  let path = `${base}/${collection}/@id:${entityId}`;

  if (options?.nested) {
    const n = options.nested;
    path += `/${n.collection}/@id:${n.entityId}`;
    if (n.property) path += `/${n.property}`;
  } else if (property) {
    path += `/${property}`;
  }

  return path;
}

/**
 * Build an ID-based path for a study-design-level entity.
 * Shorthand for common case.
 */
export function designPath(collection: string, entityId: string, property?: string): string {
  return idPath(collection, entityId, property);
}

/**
 * Build an ID-based path for a study-version-level entity.
 * Shorthand for eligibilityCriterionItems, narrativeContentItems, etc.
 */
export function versionPath(collection: string, entityId: string, property?: string): string {
  let path = `${SV}/${collection}/@id:${entityId}`;
  if (property) path += `/${property}`;
  return path;
}

/**
 * Build an ID-based path for an arbitrary base path + collection.
 * Use for top-level or non-standard collections (e.g. /administrations, /substances).
 */
export function entityPath(basePath: string, entityId: string, property?: string): string {
  let path = `${basePath}/@id:${entityId}`;
  if (property) path += `/${property}`;
  return path;
}
