import type { 
  USDMStudyDesign, 
  USDMActivity, 
  USDMEncounter, 
  USDMEpoch,
  USDMScheduleTimeline,
} from '@/stores/protocolStore';
import type { OverlayPayload } from '@/lib/overlay/schema';
import type { ProvenanceData, CellSource } from '@/lib/provenance/types';

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
}

export interface SoACell {
  activityId: string;
  visitId: string;
  mark: 'X' | 'Xa' | 'Xb' | 'O' | '' | null;
  footnoteRefs: string[];
  provenance: {
    source: CellSource;
    needsReview: boolean;
  };
}

export interface SoATableModel {
  rows: SoARow[];
  columns: SoAColumn[];
  cells: Map<string, SoACell>;
  rowGroups: { id: string; name: string; activityIds: string[] }[];
  columnGroups: { id: string; name: string; visitIds: string[] }[];
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
  };

  if (!studyDesign) return model;

  // Extract components
  const activities = studyDesign.activities ?? [];
  const encounters = studyDesign.encounters ?? [];
  const epochs = studyDesign.epochs ?? [];
  const scheduleTimelines = studyDesign.scheduleTimelines ?? [];

  // Build maps
  const activityMap = new Map(activities.map(a => [a.id, a]));
  const epochMap = new Map(epochs.map(e => [e.id, e]));

  // Build rows from activities
  const rowOrder = overlay?.table.rowOrder ?? [];
  const orderedActivities = orderItems(activities, rowOrder, 'id');
  
  // Identify parent activities (those with childIds)
  const allChildIds = new Set<string>();
  activities.forEach(a => {
    if (a.childIds) {
      a.childIds.forEach(id => allChildIds.add(id));
    }
  });

  // Build row groups from parent activities
  const parentActivities = activities.filter(a => a.childIds && a.childIds.length > 0);
  
  let rowIndex = 0;
  if (parentActivities.length > 0) {
    // Hierarchical structure
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

  // Group columns by epoch
  const epochEncounters = new Map<string, USDMEncounter[]>();
  for (const enc of orderedEncounters) {
    const epochId = enc.epochId ?? 'unknown';
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
      model.columns.push({
        id: enc.id,
        name: enc.name,
        epochId,
        epochName,
        timing: enc.timing?.windowLabel,
        order: colIndex++,
      });
    }
  }

  // Build cells from scheduleTimelines
  const activityEncounterLinks = extractActivityEncounterLinks(scheduleTimelines);
  
  for (const row of model.rows) {
    for (const col of model.columns) {
      const key = cellKey(row.id, col.id);
      const hasLink = activityEncounterLinks.has(key);
      
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
                          provenance?.cellFootnotes?.[row.id]?.[col.id] ?? [];
      
      model.cells.set(key, {
        activityId: row.id,
        visitId: col.id,
        mark: hasLink ? 'X' : null,
        footnoteRefs: Array.isArray(footnoteRefs) ? footnoteRefs : [],
        provenance: {
          source: cellProv ?? (hasLink ? 'none' : 'none'),
          needsReview: cellProv === 'needs_review' || cellProv === 'vision' || 
                       (hasLink && !cellProv),
        },
      });
    }
  }

  return model;
}

// Extract activity-encounter links from scheduleTimelines
function extractActivityEncounterLinks(
  scheduleTimelines: USDMScheduleTimeline[]
): Set<string> {
  const links = new Set<string>();

  for (const timeline of scheduleTimelines) {
    for (const instance of timeline.instances ?? []) {
      if (instance.instanceType !== 'ScheduledActivityInstance') continue;
      
      const encounterId = instance.encounterId;
      if (!encounterId) continue;

      // Handle both singular and plural activity IDs
      const activityIds = instance.activityIds ?? 
        (instance.activityId ? [instance.activityId] : []);
      
      for (const actId of activityIds) {
        links.add(cellKey(actId, encounterId));
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
