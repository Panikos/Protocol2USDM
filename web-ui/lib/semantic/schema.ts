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
