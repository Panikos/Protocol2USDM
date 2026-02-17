import type { 
  USDMStudyDesign, 
  USDMActivity, 
  USDMActivityGroup,
  USDMEncounter, 
  USDMEpoch,
  USDMScheduleTimeline,
} from '@/stores/protocolStore';
import type { OverlayPayload } from '@/lib/overlay/schema';
import type { ProvenanceData, CellSource } from '@/lib/provenance/types';
import { getExtString, getExtBoolean, hasExt, findExt, EXT_URLS } from '@/lib/extensions';

// SoA Table Model types
export interface SoARow {
  id: string;
  name: string;
  label?: string;
  groupId?: string;
  groupName?: string;
  order: number;
  isGroup: boolean;
  childIds?: string[];
}

export interface SoAColumn {
  id: string;
  name: string;
  epochId?: string;
  epochName?: string;
  timing?: string;
  order: number;
  isUnscheduled?: boolean;
}

export interface SoACell {
  activityId: string;
  visitId: string;
  mark: 'X' | 'Xa' | 'Xb' | 'Xc' | 'O' | '−' | '' | null;
  footnoteRefs: string[];
  instanceName?: string;  // Human-readable instance name (e.g., "Blood Draw @ Day 1")
  timingId?: string;      // Link to timing entity
  epochId?: string;       // Link to epoch entity
  userEdited?: boolean;   // True if cell was manually edited by user
  provenance: {
    source: CellSource;
    needsReview: boolean;
  };
}

// Enrichment instance info for display
export interface EnrichmentInstance {
  id: string;
  name: string;
  activityName?: string;
  encounterName?: string;
  scheduledDay?: number;
  epochName?: string;
}

export interface SoATableModel {
  rows: SoARow[];
  columns: SoAColumn[];
  cells: Map<string, SoACell>;
  rowGroups: { id: string; name: string; activityIds: string[] }[];
  columnGroups: { id: string; name: string; visitIds: string[] }[];
  procedureActivities: USDMActivity[];  // Activities from procedure enrichment (no SoA ticks)
  enrichmentInstances: EnrichmentInstance[];  // Instances from execution model (not in PDF SoA)
}

// Helper to check if activity is from SoA (has ticks) vs procedure enrichment
function getActivitySource(activity: USDMActivity): 'soa' | 'procedure_enrichment' | 'unknown' {
  const source = getExtString(activity.extensionAttributes, 'activitySource');
  if (source === 'soa' || source === 'procedure_enrichment') return source;
  return 'unknown';
}

// Helper to create cell key
export function cellKey(activityId: string, visitId: string): string {
  return `${activityId}|${visitId}`;
}

// Main adapter function
export function toSoATableModel(
  studyDesign: USDMStudyDesign | null,
  overlay: OverlayPayload | null,
  provenance: ProvenanceData | null
): SoATableModel {
  const model: SoATableModel = {
    rows: [],
    columns: [],
    cells: new Map(),
    rowGroups: [],
    columnGroups: [],
    procedureActivities: [],
    enrichmentInstances: [],
  };

  if (!studyDesign) return model;

  // Extract components
  const allActivities = studyDesign.activities ?? [];
  
  // Separate SoA activities from procedure enrichment activities
  const activities: USDMActivity[] = [];
  for (const activity of allActivities) {
    const source = getActivitySource(activity);
    if (source === 'procedure_enrichment') {
      model.procedureActivities.push(activity);
    } else {
      // Include 'soa' and 'unknown' (for backward compatibility)
      activities.push(activity);
    }
  }
  const activityGroups = studyDesign.activityGroups ?? [];
  const encounters = studyDesign.encounters ?? [];
  const epochs = studyDesign.epochs ?? [];
  const scheduleTimelines = studyDesign.scheduleTimelines ?? [];

  // Build maps
  const activityMap = new Map(activities.map(a => [a.id, a]));
  const epochMap = new Map(epochs.map(e => [e.id, e]));

  // Build rows from activities
  const rowOrder = overlay?.table.rowOrder ?? [];
  const orderedActivities = orderItems(activities, rowOrder, 'id');
  
  // Build activity to group mapping from activityGroups
  const activityToGroup = new Map<string, USDMActivityGroup>();
  for (const group of activityGroups) {
    for (const activityId of group.activityIds ?? []) {
      activityToGroup.set(activityId, group);
    }
  }

  // Also check for parent activities with childIds (legacy format)
  const allChildIds = new Set<string>();
  activities.forEach(a => {
    if (a.childIds) {
      a.childIds.forEach(id => allChildIds.add(id));
    }
  });
  const parentActivities = activities.filter(a => a.childIds && a.childIds.length > 0);

  let rowIndex = 0;
  
  // Build activity to group mapping from multiple sources
  // 1. activityGroupId on activity
  // 2. activityIds on group
  // 3. extensionAttributes with group info
  const activityIdToGroupId = new Map<string, string>();
  
  // Strategy 1: Check activityGroupId on each activity
  for (const activity of activities) {
    const groupId = (activity as Record<string, unknown>).activityGroupId as string | undefined;
    if (groupId) {
      activityIdToGroupId.set(activity.id, groupId);
    }
  }
  
  // Strategy 2: Check activityIds/childIds on each group
  for (const group of activityGroups) {
    // Support both activityIds (legacy) and childIds (USDM format)
    const groupActivityIds = group.activityIds ?? group.childIds ?? [];
    for (const activityId of groupActivityIds) {
      activityIdToGroupId.set(activityId, group.id);
    }
  }
  
  // Strategy 3: Check extensionAttributes for group info
  for (const activity of activities) {
    if (activityIdToGroupId.has(activity.id)) continue;
    const groupRef = getExtString(activity.extensionAttributes, 'activityGroup');
    if (groupRef) {
      const matchingGroup = activityGroups.find(g => 
        g.name.toLowerCase() === groupRef.toLowerCase() ||
        g.id === groupRef
      );
      if (matchingGroup) {
        activityIdToGroupId.set(activity.id, matchingGroup.id);
      }
    }
  }
  
  // Use activityGroups if available, otherwise fall back to parent activities
  if (activityGroups.length > 0) {
    // Group-based structure from activityGroups
    const groupedActivityIds = new Set<string>();
    const groupIdMap = new Map(activityGroups.map(g => [g.id, g]));
    
    // First, build groups with their activities
    for (const group of activityGroups) {
      // Find all activities that belong to this group
      const groupActivityIds: string[] = [];
      for (const [actId, grpId] of activityIdToGroupId) {
        if (grpId === group.id) {
          groupActivityIds.push(actId);
        }
      }
      
      model.rowGroups.push({
        id: group.id,
        name: group.name,
        activityIds: groupActivityIds.length > 0 ? groupActivityIds : (group.activityIds ?? group.childIds ?? []),
      });

      for (const activityId of groupActivityIds) {
        const activity = activityMap.get(activityId);
        if (activity) {
          model.rows.push({
            id: activity.id,
            name: activity.label ?? activity.name,
            groupId: group.id,
            groupName: group.name,
            order: rowIndex++,
            isGroup: false,
          });
          groupedActivityIds.add(activityId);
        }
      }
    }
    
    // Add ungrouped activities at the end
    for (const activity of orderedActivities) {
      if (!groupedActivityIds.has(activity.id) && !allChildIds.has(activity.id)) {
        model.rows.push({
          id: activity.id,
          name: activity.label ?? activity.name,
          order: rowIndex++,
          isGroup: false,
        });
      }
    }
  } else if (parentActivities.length > 0) {
    // Primary: Hierarchical structure from parent activities with childIds (USDM v4.0)
    for (const parent of parentActivities) {
      const groupName = parent.label ?? parent.name;
      model.rowGroups.push({
        id: parent.id,
        name: groupName,
        activityIds: parent.childIds ?? [],
      });

      for (const childId of parent.childIds ?? []) {
        const child = activityMap.get(childId);
        if (child) {
          model.rows.push({
            id: child.id,
            name: child.label ?? child.name,
            groupId: parent.id,
            groupName,
            order: rowIndex++,
            isGroup: false,
          });
        }
      }
    }

    // Add ungrouped activities (not a child, not a parent) at the end
    const parentIds = new Set(parentActivities.map(p => p.id));
    for (const activity of orderedActivities) {
      if (!allChildIds.has(activity.id) && !parentIds.has(activity.id)) {
        model.rows.push({
          id: activity.id,
          name: activity.label ?? activity.name,
          order: rowIndex++,
          isGroup: false,
        });
      }
    }
  } else {
    // Flat structure
    for (const activity of orderedActivities) {
      if (!allChildIds.has(activity.id)) {
        model.rows.push({
          id: activity.id,
          name: activity.label ?? activity.name,
          order: rowIndex++,
          isGroup: false,
        });
      }
    }
  }

  // Build columns from encounters
  const columnOrder = overlay?.table.columnOrder ?? [];
  const orderedEncounters = orderItems(encounters, columnOrder, 'id');

  // Group columns by epoch - filter out encounters without valid epochId
  const epochEncounters = new Map<string, USDMEncounter[]>();
  for (const enc of orderedEncounters) {
    const epochId = enc.epochId;
    // Skip encounters without epochId - they can't be displayed properly
    if (!epochId || !epochMap.has(epochId)) {
      continue;
    }
    if (!epochEncounters.has(epochId)) {
      epochEncounters.set(epochId, []);
    }
    epochEncounters.get(epochId)!.push(enc);
  }

  let colIndex = 0;
  for (const [epochId, encs] of epochEncounters) {
    const epoch = epochMap.get(epochId);
    const epochName = epoch?.name ?? 'Unknown Epoch';
    
    model.columnGroups.push({
      id: epochId,
      name: epochName,
      visitIds: encs.map(e => e.id),
    });

    for (const enc of encs) {
      const isUnscheduled = getExtBoolean(
        (enc as Record<string, unknown>).extensionAttributes as unknown[],
        'encounterUnscheduled'
      ) === true;
      model.columns.push({
        id: enc.id,
        name: enc.name,
        epochId,
        epochName,
        timing: enc.timing?.windowLabel,
        order: colIndex++,
        isUnscheduled,
      });
    }
  }

  // Build cells from scheduleTimelines
  const activityEncounterLinks = extractActivityEncounterLinks(scheduleTimelines);
  
  for (const row of model.rows) {
    for (const col of model.columns) {
      const key = cellKey(row.id, col.id);
      const instanceMeta = activityEncounterLinks.get(key);
      const hasLink = instanceMeta !== undefined;
      
      // Get provenance for this cell - check both formats
      // New format: provenance.cells["activityId|encounterId"]
      // Old format: provenance.activityTimepoints[activityId][encounterId]
      let cellProv: CellSource | undefined;
      if (provenance?.cells?.[key]) {
        cellProv = provenance.cells[key] as CellSource;
      } else if (provenance?.activityTimepoints?.[row.id]?.[col.id]) {
        cellProv = provenance.activityTimepoints[row.id][col.id] as CellSource;
      }
      
      // Get footnotes - check both formats
      const footnoteRefs = provenance?.cellFootnotes?.[key] ?? 
                          (provenance?.cellFootnotes?.[row.id] as Record<string, string[]> | undefined)?.[col.id] ?? [];
      
      // Determine provenance source:
      // - If provenance exists, use it
      // - If link exists but no provenance AND it's an enrichment instance, don't mark as orphan
      // - If link exists but no provenance AND it's NOT enrichment, mark as orphan ('none')
      const isEnrichmentCell = instanceMeta?.isEnrichment ?? false;
      let effectiveSource: CellSource;
      if (cellProv) {
        effectiveSource = cellProv;
      } else if (hasLink && isEnrichmentCell) {
        // Enrichment instances don't need SoA provenance - mark as confirmed
        effectiveSource = 'both';
      } else if (hasLink) {
        // SoA instance without provenance - orphan
        effectiveSource = 'none';
      } else {
        effectiveSource = 'none';
      }

      // Determine cell mark priority:
      // 1. From USDM extensionAttributes (user-edited cells)
      // 2. Default 'X' if ScheduledActivityInstance exists
      // 3. 'X' if provenance indicates a cell should exist
      // 4. null if no data
      let cellMark: 'X' | 'Xa' | 'Xb' | 'Xc' | 'O' | '−' | '' | null = null;
      if (hasLink) {
        // ScheduledActivityInstance exists - use its mark or default to X
        cellMark = instanceMeta?.mark ?? 'X';
      } else if (cellProv && cellProv !== 'none') {
        // No instance but provenance says cell exists - show X
        cellMark = 'X';
      }
      
      // Use footnoteRefs from USDM if available, fall back to provenance footnotes
      const cellFootnoteRefs = (instanceMeta?.footnoteRefs?.length ? instanceMeta.footnoteRefs : null)
        ?? (Array.isArray(footnoteRefs) ? footnoteRefs : []);
      // Track if cell was user-edited (from USDM extensionAttributes)
      const cellUserEdited = instanceMeta?.userEdited ?? false;
      
      model.cells.set(key, {
        activityId: row.id,
        visitId: col.id,
        mark: cellMark,
        footnoteRefs: cellFootnoteRefs,
        instanceName: instanceMeta?.name,
        timingId: instanceMeta?.timingId,
        epochId: instanceMeta?.epochId,
        userEdited: cellUserEdited,
        provenance: {
          source: effectiveSource,
          needsReview: cellProv === 'needs_review' || cellProv === 'vision' || 
                       (hasLink && !cellProv && !isEnrichmentCell),
        },
      });
    }
  }

  // Extract enrichment instances for separate display
  const allActivityMap = new Map(allActivities.map(a => [a.id, a]));
  const encounterMap = new Map(encounters.map(e => [e.id, e]));
  // Note: epochMap already defined above
  
  for (const timeline of scheduleTimelines) {
    for (const instance of timeline.instances ?? []) {
      if (instance.instanceType !== 'ScheduledActivityInstance') continue;
      if (!isEnrichmentInstance(instance as Record<string, unknown>)) continue;
      
      // Get activity names
      const activityNames = (instance.activityIds ?? [])
        .map(id => allActivityMap.get(id)?.name || allActivityMap.get(id)?.label)
        .filter(Boolean)
        .join(', ');
      
      // Get encounter name
      const encounter = instance.encounterId ? encounterMap.get(instance.encounterId) : undefined;
      const encounterName = encounter?.name;
      
      // Get epoch name
      const epoch = instance.epochId ? epochMap.get(instance.epochId) : undefined;
      const epochName = epoch?.name;
      
      model.enrichmentInstances.push({
        id: instance.id,
        name: instance.name || `Instance ${instance.id.substring(0, 8)}`,
        activityName: activityNames || undefined,
        encounterName,
        scheduledDay: instance.scheduledDay as number | undefined,
        epochName,
      });
    }
  }

  return model;
}

// Instance metadata for enhanced cell display
interface InstanceMeta {
  name?: string;
  timingId?: string;
  epochId?: string;
}

// Check if instance is from execution model enrichment (not original SoA)
function isEnrichmentInstance(instance: Record<string, unknown>): boolean {
  return getExtString(instance.extensionAttributes as unknown[], 'instanceSource') === 'execution_model';
}

// Instance metadata for enhanced cell display
interface InstanceMetaWithSource extends InstanceMeta {
  isEnrichment: boolean;
  mark?: 'X' | 'Xa' | 'Xb' | 'Xc' | 'O' | '−' | null;
  footnoteRefs?: string[];
  userEdited?: boolean;
}

// Extract activity-encounter links from scheduleTimelines with metadata
function extractActivityEncounterLinks(
  scheduleTimelines: USDMScheduleTimeline[]
): Map<string, InstanceMetaWithSource> {
  const links = new Map<string, InstanceMetaWithSource>();

  for (const timeline of scheduleTimelines) {
    for (const instance of timeline.instances ?? []) {
      if (instance.instanceType !== 'ScheduledActivityInstance') continue;
      
      const encounterId = instance.encounterId;
      if (!encounterId) continue;

      // Check if this is an enrichment instance
      const isEnrichment = getExtString(instance.extensionAttributes, 'instanceSource') === 'execution_model';

      // Handle both singular and plural activity IDs
      const activityIds = instance.activityIds ?? 
        (instance.activityId ? [instance.activityId] : []);
      
      // Extract mark and userEdited from extensionAttributes
      let mark: 'X' | 'Xa' | 'Xb' | 'Xc' | 'O' | '−' | null = 'X'; // Default to X if instance exists
      let footnoteRefs: string[] = [];
      let userEdited = false;
      const exts = instance.extensionAttributes;
      if (exts && exts.length > 0) {
        const cellMarkVal = getExtString(exts, 'soaCellMark');
        if (cellMarkVal) {
          if (cellMarkVal === 'X' || cellMarkVal === 'Xa' || cellMarkVal === 'Xb' || cellMarkVal === 'Xc' || cellMarkVal === 'O' || cellMarkVal === '−') {
            mark = cellMarkVal;
          } else if (cellMarkVal === 'clear') {
            mark = null;
          }
        }
        const fnRefsVal = getExtString(exts, 'soaFootnoteRefs');
        if (fnRefsVal) {
          try {
            footnoteRefs = JSON.parse(fnRefsVal);
          } catch { /* ignore parse errors */ }
        }
        userEdited = getExtBoolean(exts, 'userEdited') === true;
      }

      for (const actId of activityIds) {
        const key = cellKey(actId, encounterId);
        // Don't overwrite SoA instance with enrichment instance
        if (links.has(key) && isEnrichment) continue;
        links.set(key, {
          name: instance.name,
          timingId: instance.timingId as string | undefined,
          epochId: instance.epochId,
          isEnrichment,
          mark,
          footnoteRefs,
          userEdited,
        });
      }
    }
  }

  return links;
}

// Order items according to overlay order, preserving original order for missing items
function orderItems<T extends { id: string }>(
  items: T[],
  order: string[],
  idKey: keyof T
): T[] {
  if (order.length === 0) return items;

  const orderMap = new Map(order.map((id, idx) => [id, idx]));
  
  return [...items].sort((a, b) => {
    const aOrder = orderMap.get(a[idKey] as string) ?? Infinity;
    const bOrder = orderMap.get(b[idKey] as string) ?? Infinity;
    return aOrder - bOrder;
  });
}

// Get flat row data for AG Grid
export function getRowDataForGrid(model: SoATableModel): Record<string, unknown>[] {
  return model.rows.map(row => {
    const rowData: Record<string, unknown> = {
      id: row.id,
      activityName: row.name,
      groupName: row.groupName ?? '',
    };

    // Add cell values for each column
    for (const col of model.columns) {
      const cell = model.cells.get(cellKey(row.id, col.id));
      rowData[`col_${col.id}`] = cell?.mark ?? '';
    }

    return rowData;
  });
}

// Get column definitions for AG Grid
export function getColumnDefsForGrid(model: SoATableModel): unknown[] {
  const columnDefs: unknown[] = [];

  // Group column
  if (model.rowGroups.length > 0) {
    columnDefs.push({
      headerName: 'Category',
      field: 'groupName',
      pinned: 'left',
      width: 150,
      rowGroup: true,
      hide: true,
    });
  }

  // Activity name column
  columnDefs.push({
    headerName: 'Activity',
    field: 'activityName',
    pinned: 'left',
    width: 200,
  });

  // Group columns by epoch
  for (const group of model.columnGroups) {
    const children = model.columns
      .filter(col => col.epochId === group.id)
      .map(col => ({
        headerName: col.timing ?? col.name,
        field: `col_${col.id}`,
        width: 80,
        cellRenderer: 'provenanceCellRenderer',
        cellRendererParams: {
          columnId: col.id,
        },
      }));

    columnDefs.push({
      headerName: group.name,
      children,
    });
  }

  return columnDefs;
}
