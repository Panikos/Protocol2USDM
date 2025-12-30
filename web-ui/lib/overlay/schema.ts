import { z } from 'zod';

// Node position in diagram
export const NodePositionSchema = z.object({
  x: z.number(),
  y: z.number(),
  locked: z.boolean().optional().default(false),
  highlight: z.boolean().optional(),
  icon: z.string().optional(),
});

// Edge style configuration
export const EdgeStyleSchema = z.object({
  style: z.enum(['solid', 'dashed', 'dotted']).optional(),
  color: z.string().optional(),
});

// Diagram globals
export const DiagramGlobalsSchema = z.object({
  snapGrid: z.number().default(5),
  zoom: z.number().optional(),
  pan: z.object({ x: z.number(), y: z.number() }).optional(),
});

// Diagram overlay
export const DiagramOverlaySchema = z.object({
  nodes: z.record(z.string(), NodePositionSchema),
  edges: z.record(z.string(), EdgeStyleSchema).optional(),
  globals: DiagramGlobalsSchema.optional(),
});

// Row group for table
export const RowGroupSchema = z.object({
  label: z.string(),
  activityIds: z.array(z.string()),
});

// Column group for table
export const ColumnGroupSchema = z.object({
  label: z.string(),
  visitIds: z.array(z.string()),
});

// Table overlay
export const TableOverlaySchema = z.object({
  rowOrder: z.array(z.string()).optional(),
  columnOrder: z.array(z.string()).optional(),
  rowGroups: z.array(RowGroupSchema).optional(),
  columnGroups: z.array(ColumnGroupSchema).optional(),
  hiddenColumns: z.array(z.string()).optional(),
});

// Combined overlay payload
export const OverlayPayloadSchema = z.object({
  diagram: DiagramOverlaySchema,
  table: TableOverlaySchema,
});

// Full overlay document
export const OverlayDocSchema = z.object({
  version: z.number().default(1),
  protocolId: z.string(),
  usdmRevision: z.string(),
  status: z.enum(['draft', 'published']),
  updatedAt: z.string().datetime(),
  updatedBy: z.string(),
  basePublishedId: z.string().optional(),
  payload: OverlayPayloadSchema,
});

// Export types
export type NodePosition = z.infer<typeof NodePositionSchema>;
export type EdgeStyle = z.infer<typeof EdgeStyleSchema>;
export type DiagramGlobals = z.infer<typeof DiagramGlobalsSchema>;
export type DiagramOverlay = z.infer<typeof DiagramOverlaySchema>;
export type RowGroup = z.infer<typeof RowGroupSchema>;
export type ColumnGroup = z.infer<typeof ColumnGroupSchema>;
export type TableOverlay = z.infer<typeof TableOverlaySchema>;
export type OverlayPayload = z.infer<typeof OverlayPayloadSchema>;
export type OverlayDoc = z.infer<typeof OverlayDocSchema>;

// Factory function to create empty overlay
export function createEmptyOverlay(
  protocolId: string,
  usdmRevision: string,
  userId: string
): OverlayDoc {
  return {
    version: 1,
    protocolId,
    usdmRevision,
    status: 'draft',
    updatedAt: new Date().toISOString(),
    updatedBy: userId,
    payload: {
      diagram: {
        nodes: {},
        edges: {},
        globals: { snapGrid: 5 },
      },
      table: {
        rowOrder: [],
        columnOrder: [],
        rowGroups: [],
        columnGroups: [],
        hiddenColumns: [],
      },
    },
  };
}
