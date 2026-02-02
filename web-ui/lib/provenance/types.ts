import { z } from 'zod';

// Cell source types
export type CellSource = 'text' | 'vision' | 'both' | 'needs_review' | 'none';

// Bounding box for PDF highlighting
export const BoundingBoxSchema = z.object({
  page: z.number(),
  x: z.number(),
  y: z.number(),
  width: z.number(),
  height: z.number(),
});

export type BoundingBox = z.infer<typeof BoundingBoxSchema>;

// Entity-level provenance
export const EntityProvenanceSchema = z.object({
  source: z.enum(['text', 'vision', 'both']),
  confidence: z.number().optional(),
  pageRefs: z.array(z.number()).optional(),
  boundingBox: BoundingBoxSchema.optional(),
});

export type EntityProvenance = z.infer<typeof EntityProvenanceSchema>;

// Full provenance data structure
export const ProvenanceDataSchema = z.object({
  // New format: entities object with activity/encounter sources
  entities: z.object({
    activities: z.record(z.string(), z.enum(['text', 'vision', 'both'])).optional(),
    plannedTimepoints: z.record(z.string(), z.enum(['text', 'vision', 'both'])).optional(),
    encounters: z.record(z.string(), z.enum(['text', 'vision', 'both'])).optional(),
    epochs: z.record(z.string(), z.enum(['text', 'vision', 'both'])).optional(),
    activityGroups: z.record(z.string(), z.enum(['text', 'vision', 'both'])).optional(),
  }).optional(),
  
  // New format: cells as flat map "activityId|encounterId" -> source
  cells: z.record(
    z.string(), // "activityId|encounterId"
    z.enum(['text', 'vision', 'both', 'needs_review'])
  ).optional(),
  
  // Legacy format: Entity-level provenance
  activities: z.record(z.string(), EntityProvenanceSchema).optional(),
  plannedTimepoints: z.record(z.string(), EntityProvenanceSchema).optional(),
  encounters: z.record(z.string(), EntityProvenanceSchema).optional(),
  epochs: z.record(z.string(), EntityProvenanceSchema).optional(),
  
  // Legacy format: Cell-level provenance (activity × timepoint)
  activityTimepoints: z.record(
    z.string(), // activityId
    z.record(z.string(), z.enum(['text', 'vision', 'both', 'needs_review'])) // timepointId → source
  ).optional(),
  
  // Footnote references per cell (supports both formats)
  cellFootnotes: z.union([
    z.record(z.string(), z.array(z.string())), // New: "activityId|encounterId" -> refs
    z.record(z.string(), z.record(z.string(), z.array(z.string()))) // Legacy: nested
  ]).optional(),
  
  // SoA footnotes
  footnotes: z.array(z.string()).optional(),
});

export type ProvenanceData = z.infer<typeof ProvenanceDataSchema>;

// Provenance statistics
export interface ProvenanceStats {
  confirmed: number;
  textOnly: number;
  visionOnly: number;
  needsReview: number;
  orphaned: number;
  total: number;
}

// Helper to calculate provenance stats
export function calculateProvenanceStats(provenance: ProvenanceData | null): ProvenanceStats {
  const stats: ProvenanceStats = {
    confirmed: 0,
    textOnly: 0,
    visionOnly: 0,
    needsReview: 0,
    orphaned: 0,
    total: 0,
  };

  if (!provenance) return stats;

  // New format: provenance.cells
  if (provenance.cells) {
    for (const source of Object.values(provenance.cells)) {
      stats.total++;
      switch (source) {
        case 'both':
          stats.confirmed++;
          break;
        case 'text':
          stats.textOnly++;
          break;
        case 'vision':
          stats.visionOnly++;
          break;
        case 'needs_review':
          stats.needsReview++;
          break;
      }
    }
    return stats;
  }

  // Legacy format: provenance.activityTimepoints
  if (provenance.activityTimepoints) {
    for (const activityCells of Object.values(provenance.activityTimepoints)) {
      for (const source of Object.values(activityCells)) {
        stats.total++;
        switch (source) {
          case 'both':
            stats.confirmed++;
            break;
          case 'text':
            stats.textOnly++;
            break;
          case 'vision':
          case 'needs_review':
            stats.needsReview++;
            break;
        }
      }
    }
  }

  return stats;
}

// Get provenance color class
export function getProvenanceColorClass(source: CellSource): string {
  switch (source) {
    case 'both':
      return 'cell-confirmed';
    case 'text':
      return 'cell-text-only';
    case 'vision':
    case 'needs_review':
      return 'cell-vision-only';
    case 'none':
      return 'cell-orphaned';
    default:
      return '';
  }
}

// Get provenance hex color
export function getProvenanceColor(source: CellSource): string {
  switch (source) {
    case 'both':
      return '#4ade80';
    case 'text':
      return '#60a5fa';
    case 'vision':
    case 'needs_review':
      return '#fb923c';
    case 'none':
      return '#f87171';
    default:
      return 'transparent';
  }
}
