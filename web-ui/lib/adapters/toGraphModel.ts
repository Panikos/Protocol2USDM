import type { 
  USDMStudyDesign, 
  USDMActivity, 
  USDMEncounter, 
  USDMEpoch,
  USDMScheduleTimeline,
  USDMScheduledInstance,
  USDMTiming,
} from '@/stores/protocolStore';
import type { OverlayPayload, NodePosition } from '@/lib/overlay/schema';

// Cytoscape node types
export type NodeType = 'instance' | 'timing' | 'activity' | 'condition' | 'halo' | 'epoch' | 'anchor';

// Timing type codes from CDISC
const TIMING_TYPE = {
  BEFORE: 'C201357',
  AFTER: 'C201356',
  FIXED_REFERENCE: 'C201358',  // This is an anchor
};

export interface CytoscapeNode {
  data: {
    id: string;
    label: string;
    type: NodeType;
    usdmRef: string;
    epochId?: string;
    encounterId?: string;
    activityId?: string;
    // Timing-specific data
    timingType?: string;  // Before, After, Fixed Reference
    timingValue?: string;  // e.g., "7 days"
    windowLabel?: string;  // e.g., "-2..2 days"
    isAnchor?: boolean;
    fromInstanceId?: string;
    toInstanceId?: string;
  };
  position: { x: number; y: number };
  locked?: boolean;
  classes?: string;
}

export interface CytoscapeEdge {
  data: {
    id: string;
    source: string;
    target: string;
    type: 'timing' | 'activity' | 'condition' | 'sequence';
    label?: string;
  };
  classes?: string;
}

export interface ValidationError {
  type: 'missing_endpoint' | 'duplicate_id' | 'invalid_position';
  message: string;
  nodeId?: string;
  edgeId?: string;
}

export interface GraphModel {
  nodes: CytoscapeNode[];
  edges: CytoscapeEdge[];
  validation: {
    valid: boolean;
    errors: ValidationError[];
  };
}

// Default layout configuration
const DEFAULT_SPACING = {
  epochWidth: 250,
  encounterSpacing: 150,
  activitySpacing: 80,
  startX: 100,
  startY: 100,
};

// Main adapter function
export function toGraphModel(
  studyDesign: USDMStudyDesign | null,
  overlay: OverlayPayload | null
): GraphModel {
  const model: GraphModel = {
    nodes: [],
    edges: [],
    validation: { valid: true, errors: [] },
  };

  if (!studyDesign) return model;

  const epochs = studyDesign.epochs ?? [];
  const encounters = studyDesign.encounters ?? [];
  const activities = studyDesign.activities ?? [];
  const scheduleTimelines = studyDesign.scheduleTimelines ?? [];

  // Build maps
  const epochMap = new Map(epochs.map(e => [e.id, e]));
  const encounterMap = new Map(encounters.map(e => [e.id, e]));
  const activityMap = new Map(activities.map(a => [a.id, a]));

  // Track node IDs for validation
  const nodeIds = new Set<string>();
  
  // Generate epoch nodes (background grouping)
  let epochX = DEFAULT_SPACING.startX;
  const epochPositions = new Map<string, { x: number; width: number }>();

  for (const epoch of epochs) {
    const encountersInEpoch = encounters.filter(e => e.epochId === epoch.id);
    const width = Math.max(
      DEFAULT_SPACING.epochWidth,
      encountersInEpoch.length * DEFAULT_SPACING.encounterSpacing
    );

    epochPositions.set(epoch.id, { x: epochX, width });

    const nodeId = `epoch_${epoch.id}`;
    const position = getNodePosition(nodeId, overlay, { 
      x: epochX + width / 2, 
      y: DEFAULT_SPACING.startY - 50 
    });

    model.nodes.push({
      data: {
        id: nodeId,
        label: epoch.name,
        type: 'epoch',
        usdmRef: epoch.id,
      },
      position,
      locked: overlay?.diagram.nodes[nodeId]?.locked,
      classes: 'epoch-node',
    });

    nodeIds.add(nodeId);
    epochX += width + 50;
  }

  // Generate encounter/timing nodes
  const encounterPositions = new Map<string, { x: number; y: number }>();

  for (const epoch of epochs) {
    const epochPos = epochPositions.get(epoch.id);
    if (!epochPos) continue;

    const encountersInEpoch = encounters.filter(e => e.epochId === epoch.id);
    let encX = epochPos.x;

    for (const enc of encountersInEpoch) {
      const nodeId = `enc_${enc.id}`;
      const defaultPos = { x: encX, y: DEFAULT_SPACING.startY + 50 };
      const position = getNodePosition(nodeId, overlay, defaultPos);

      encounterPositions.set(enc.id, position);

      model.nodes.push({
        data: {
          id: nodeId,
          label: enc.timing?.windowLabel ?? enc.name,
          type: 'timing',
          usdmRef: enc.id,
          epochId: epoch.id,
          encounterId: enc.id,
        },
        position,
        locked: overlay?.diagram.nodes[nodeId]?.locked,
        classes: overlay?.diagram.nodes[nodeId]?.highlight ? 'highlighted' : undefined,
      });

      nodeIds.add(nodeId);
      encX += DEFAULT_SPACING.encounterSpacing;
    }
  }

  // Generate sequence edges between encounters
  for (let i = 0; i < encounters.length - 1; i++) {
    const current = encounters[i];
    const next = encounters[i + 1];

    model.edges.push({
      data: {
        id: `seq_${current.id}_${next.id}`,
        source: `enc_${current.id}`,
        target: `enc_${next.id}`,
        type: 'sequence',
      },
    });
  }

  // Generate activity instance nodes from scheduleTimelines
  const instancesByEncounter = new Map<string, USDMScheduledInstance[]>();

  for (const timeline of scheduleTimelines) {
    for (const instance of timeline.instances ?? []) {
      if (instance.instanceType !== 'ScheduledActivityInstance') continue;
      if (!instance.encounterId) continue;

      if (!instancesByEncounter.has(instance.encounterId)) {
        instancesByEncounter.set(instance.encounterId, []);
      }
      instancesByEncounter.get(instance.encounterId)!.push(instance);
    }
  }

  // Create activity nodes below their encounters
  for (const [encounterId, instances] of instancesByEncounter) {
    const encPos = encounterPositions.get(encounterId);
    if (!encPos) continue;

    let actY = encPos.y + 100;

    for (const instance of instances) {
      const activityIds = instance.activityIds ?? 
        (instance.activityId ? [instance.activityId] : []);

      for (const actId of activityIds) {
        const activity = activityMap.get(actId);
        if (!activity) continue;

        const nodeId = `act_${instance.id}_${actId}`;
        const defaultPos = { x: encPos.x, y: actY };
        const position = getNodePosition(nodeId, overlay, defaultPos);

        model.nodes.push({
          data: {
            id: nodeId,
            label: activity.label ?? activity.name,
            type: 'activity',
            usdmRef: actId,
            encounterId,
            activityId: actId,
          },
          position,
          locked: overlay?.diagram.nodes[nodeId]?.locked,
          classes: overlay?.diagram.nodes[nodeId]?.highlight ? 'highlighted' : undefined,
        });

        nodeIds.add(nodeId);

        // Edge from encounter to activity
        model.edges.push({
          data: {
            id: `link_${encounterId}_${actId}`,
            source: `enc_${encounterId}`,
            target: nodeId,
            type: 'activity',
          },
        });

        actY += DEFAULT_SPACING.activitySpacing;
      }
    }
  }

  // Generate timing nodes from studyDesign.timings (root level)
  const timings = studyDesign.timings ?? [];
  const TIMING_Y_OFFSET = 200;  // Position below encounters
  
  for (let i = 0; i < timings.length; i++) {
    const timing = timings[i];
    
    // Position timings in a row below the timeline
    const timingX = DEFAULT_SPACING.startX + i * 140;
    const timingY = DEFAULT_SPACING.startY + TIMING_Y_OFFSET;
    
    // Determine timing type - handle both simple string and CDISC object format
    const timingTypeRaw = timing.type;
    let timingTypeStr = 'Timing';
    let isAnchor = false;
    
    if (typeof timingTypeRaw === 'string') {
      timingTypeStr = timingTypeRaw;
      // Check if this is an anchor-type timing
      isAnchor = timingTypeRaw === 'Fixed Reference' || timingTypeRaw === 'Anchor';
    } else if (timingTypeRaw && typeof timingTypeRaw === 'object') {
      timingTypeStr = timingTypeRaw.decode ?? 'Timing';
      isAnchor = timingTypeRaw.code === TIMING_TYPE.FIXED_REFERENCE;
    }
    
    const nodeId = `timing_${timing.id}`;
    const defaultPos = { x: timingX, y: timingY };
    const position = getNodePosition(nodeId, overlay, defaultPos);
    
    // Build value label
    let valueLabel = timing.valueLabel;
    if (!valueLabel && timing.value !== undefined) {
      const unit = timing.unit ?? '';
      valueLabel = `${timing.value} ${unit}`.trim();
    }
    
    // Build window label
    let windowLabel = timing.windowLabel;
    if (!windowLabel && (timing.windowLower !== undefined || timing.windowUpper !== undefined)) {
      const lower = timing.windowLower ?? 0;
      const upper = timing.windowUpper ?? 0;
      const unit = timing.unit ?? 'days';
      windowLabel = `${lower}..${upper} ${unit}`;
    }
    
    // Build label with timing info
    const labelParts: string[] = [];
    if (isAnchor) {
      labelParts.push('⚓');  // Anchor icon
    }
    if (timing.name) labelParts.push(timing.name);
    if (valueLabel) labelParts.push(valueLabel);
    if (windowLabel) labelParts.push(`(${windowLabel})`);
    if (timing.relativeTo) labelParts.push(`→ ${timing.relativeTo}`);
    const label = labelParts.join('\n') || 'Timing';
    
    model.nodes.push({
      data: {
        id: nodeId,
        label,
        type: isAnchor ? 'anchor' : 'timing',
        usdmRef: timing.id,
        timingType: timingTypeStr,
        timingValue: valueLabel,
        windowLabel,
        isAnchor,
      },
      position,
      locked: overlay?.diagram.nodes[nodeId]?.locked,
      classes: isAnchor ? 'anchor-node' : 'timing-detail-node',
    });
    
    nodeIds.add(nodeId);
  }

  // Validate the graph
  model.validation = validateGraph(model, nodeIds);

  return model;
}

// Get node position from overlay or use default
function getNodePosition(
  nodeId: string,
  overlay: OverlayPayload | null,
  defaultPos: { x: number; y: number }
): { x: number; y: number } {
  const overlayPos = overlay?.diagram.nodes[nodeId];
  if (overlayPos && typeof overlayPos.x === 'number' && typeof overlayPos.y === 'number') {
    return { x: overlayPos.x, y: overlayPos.y };
  }
  return defaultPos;
}

// Validate graph integrity
function validateGraph(
  model: GraphModel,
  nodeIds: Set<string>
): { valid: boolean; errors: ValidationError[] } {
  const errors: ValidationError[] = [];

  // Check for duplicate node IDs
  const seenIds = new Set<string>();
  for (const node of model.nodes) {
    if (seenIds.has(node.data.id)) {
      errors.push({
        type: 'duplicate_id',
        message: `Duplicate node ID: ${node.data.id}`,
        nodeId: node.data.id,
      });
    }
    seenIds.add(node.data.id);
  }

  // Check edge endpoints exist
  for (const edge of model.edges) {
    if (!nodeIds.has(edge.data.source)) {
      errors.push({
        type: 'missing_endpoint',
        message: `Edge source not found: ${edge.data.source}`,
        edgeId: edge.data.id,
      });
    }
    if (!nodeIds.has(edge.data.target)) {
      errors.push({
        type: 'missing_endpoint',
        message: `Edge target not found: ${edge.data.target}`,
        edgeId: edge.data.id,
      });
    }
  }

  // Check positions are valid numbers
  for (const node of model.nodes) {
    if (typeof node.position.x !== 'number' || isNaN(node.position.x) ||
        typeof node.position.y !== 'number' || isNaN(node.position.y)) {
      errors.push({
        type: 'invalid_position',
        message: `Invalid position for node: ${node.data.id}`,
        nodeId: node.data.id,
      });
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

// Convert to Cytoscape elements format
export function toCytoscapeElements(model: GraphModel): cytoscape.ElementDefinition[] {
  const elements: cytoscape.ElementDefinition[] = [];

  for (const node of model.nodes) {
    elements.push({
      group: 'nodes',
      data: node.data,
      position: node.position,
      locked: node.locked,
      classes: node.classes,
    });
  }

  for (const edge of model.edges) {
    elements.push({
      group: 'edges',
      data: edge.data,
      classes: edge.classes,
    });
  }

  return elements;
}
