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
  // Entity-level provenance
  activities: z.record(z.string(), EntityProvenanceSchema).optional(),
  plannedTimepoints: z.record(z.string(), EntityProvenanceSchema).optional(),
  encounters: z.record(z.string(), EntityProvenanceSchema).optional(),
  epochs: z.record(z.string(), EntityProvenanceSchema).optional(),
  
  // Cell-level provenance (activity × timepoint)
  activityTimepoints: z.record(
    z.string(), // activityId
    z.record(z.string(), z.enum(['text', 'vision', 'both', 'needs_review'])) // timepointId → source
  ).optional(),
  
  // Footnote references per cell
  cellFootnotes: z.record(
    z.string(), // activityId
    z.record(z.string(), z.array(z.string())) // timepointId → footnote refs
  ).optional(),
  
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

  if (!provenance?.activityTimepoints) return stats;

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
