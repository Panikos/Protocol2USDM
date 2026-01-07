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

// Helper to combine class names
function cn(...classes: (string | boolean | undefined | null)[]): string | undefined {
  const result = classes.filter(Boolean).join(' ');
  return result || undefined;
}

// Execution model types
export interface TimeAnchor {
  id: string;
  definition: string;
  anchorType: string;
  dayValue?: number;
  sourceText?: string;
}

export interface Repetition {
  id: string;
  type: string;
  interval?: string;
  startOffset?: string;
  endOffset?: string;
  activityId?: string;
  sourceText?: string;
}

export interface VisitWindow {
  encounterId: string;
  windowLower?: number;
  windowUpper?: number;
  windowLabel?: string;
}

export interface TraversalConstraint {
  id: string;
  requiredSequence?: string[];
  allowEarlyExit?: boolean;
  exitEpochIds?: string[];
  mandatoryVisits?: string[];
}

export interface ExecutionModelData {
  timeAnchors?: TimeAnchor[];
  repetitions?: Repetition[];
  visitWindows?: VisitWindow[];
  traversalConstraints?: TraversalConstraint[];
}

// Cytoscape node types
export type NodeType = 'instance' | 'timing' | 'activity' | 'condition' | 'halo' | 'epoch' | 'anchor' | 'window' | 'repetition' | 'swimlane';

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
    // Visit window data
    hasWindow?: boolean;
    parentEncounter?: string;
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
    type: 'timing' | 'activity' | 'condition' | 'sequence' | 'transition' | 'window';
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
  epochWidth: 300,
  encounterSpacing: 160,  // Increased from 120 for wider activity boxes
  activitySpacing: 55,    // Vertical spacing between activities (box height 45 + 10 gap)
  startX: 80,
  startY: 120,
  swimlaneHeight: 600,
  anchorY: 50,
  epochHeaderHeight: 50,
  encounterY: 150,
  activityStartY: 250,
};

// Main adapter function
export function toGraphModel(
  studyDesign: USDMStudyDesign | null,
  overlay: OverlayPayload | null,
  executionModel?: ExecutionModelData | null
): GraphModel {
  const model: GraphModel = {
    nodes: [],
    edges: [],
    validation: { valid: true, errors: [] },
  };

  if (!studyDesign) return model;

  const allEpochs = studyDesign.epochs ?? [];
  const encounters = studyDesign.encounters ?? [];
  const activities = studyDesign.activities ?? [];
  const scheduleTimelines = studyDesign.scheduleTimelines ?? [];

  // Filter epochs based on traversal constraints if available
  // This shows only the main epoch flow (like traversal view does)
  let epochs = allEpochs;
  const traversalConstraint = executionModel?.traversalConstraints?.[0];
  if (traversalConstraint?.requiredSequence && traversalConstraint.requiredSequence.length > 0) {
    const requiredSequence = traversalConstraint.requiredSequence;
    
    // Build name-based lookup for fallback matching
    const epochByName = new Map<string, string>();
    for (const epoch of allEpochs) {
      const normalized = epoch.name.toUpperCase().replace(/[\s-]/g, '_');
      const stripped = epoch.name.toUpperCase().replace(/[\s_-]/g, ''); // No separators
      epochByName.set(normalized, epoch.id);
      epochByName.set(stripped, epoch.id);
      epochByName.set(epoch.name.toUpperCase(), epoch.id);
      epochByName.set(epoch.name.toLowerCase(), epoch.id);
    }
    
    // Map epoch references to actual epoch IDs
    const filteredEpochIds = new Set<string>();
    for (const seqId of requiredSequence) {
      // 1. epoch_N format -> index lookup
      const match = seqId.match(/epoch_(\d+)/);
      if (match) {
        const idx = parseInt(match[1], 10) - 1;
        if (allEpochs[idx]) {
          filteredEpochIds.add(allEpochs[idx].id);
        }
        continue;
      }
      
      // 2. Direct UUID reference
      if (allEpochs.some(e => e.id === seqId)) {
        filteredEpochIds.add(seqId);
        continue;
      }
      
      // 3. Name-based fallback (handles "SCREENING", "washout", "WASHOUT", etc.)
      const normalized = seqId.toUpperCase().replace(/[\s-]/g, '_');
      const stripped = seqId.toUpperCase().replace(/[\s_-]/g, ''); // No separators
      const matchedId = epochByName.get(normalized) || epochByName.get(stripped) || epochByName.get(seqId.toUpperCase()) || epochByName.get(seqId.toLowerCase());
      if (matchedId) {
        filteredEpochIds.add(matchedId);
      }
    }
    
    // Only filter if we found at least one valid epoch (graceful fallback)
    if (filteredEpochIds.size > 0) {
      epochs = allEpochs.filter(e => filteredEpochIds.has(e.id));
    }
    // If no epochs matched, keep all epochs (don't show blank graph)
  }

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
    // Center epoch box directly above the first encounter in this epoch
    // Epoch center X = first encounter X (both use epochX as starting point)
    const position = getNodePosition(nodeId, overlay, { 
      x: epochX, 
      y: DEFAULT_SPACING.epochHeaderHeight 
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

  // Generate encounter/timing nodes with visit windows
  const encounterPositions = new Map<string, { x: number; y: number }>();

  for (const epoch of epochs) {
    const epochPos = epochPositions.get(epoch.id);
    if (!epochPos) continue;

    const encountersInEpoch = encounters.filter(e => e.epochId === epoch.id);
    let encX = epochPos.x;

    for (const enc of encountersInEpoch) {
      const nodeId = `enc_${enc.id}`;
      const defaultPos = { x: encX, y: DEFAULT_SPACING.encounterY };
      const position = getNodePosition(nodeId, overlay, defaultPos);

      encounterPositions.set(enc.id, position);

      // Check for visit window from execution model or encounter timing
      const hasWindow = Boolean(enc.timing?.windowLabel || 
        (enc.timing && (enc.timing as Record<string, unknown>).windowLower !== undefined));
      
      model.nodes.push({
        data: {
          id: nodeId,
          label: enc.name,
          type: 'timing',
          usdmRef: enc.id,
          epochId: epoch.id,
          encounterId: enc.id,
          windowLabel: enc.timing?.windowLabel,
          hasWindow,
        },
        position,
        locked: overlay?.diagram.nodes[nodeId]?.locked,
        classes: cn(
          overlay?.diagram.nodes[nodeId]?.highlight && 'highlighted',
          hasWindow && 'has-window'
        ),
      });

      nodeIds.add(nodeId);
      
      // Add visit window indicator node if window exists
      if (hasWindow && enc.timing?.windowLabel) {
        const windowNodeId = `window_${enc.id}`;
        const windowPos = { x: position.x, y: position.y - 30 };
        
        model.nodes.push({
          data: {
            id: windowNodeId,
            label: enc.timing.windowLabel,
            type: 'window',
            usdmRef: enc.id,
            parentEncounter: enc.id,
          },
          position: getNodePosition(windowNodeId, overlay, windowPos),
          classes: 'window-node',
        });
        
        nodeIds.add(windowNodeId);
        
        // Edge from window to encounter
        model.edges.push({
          data: {
            id: `window_edge_${enc.id}`,
            source: windowNodeId,
            target: nodeId,
            type: 'window',
          },
          classes: 'window-edge',
        });
      }
      
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

        // Use instance name if available (human-readable format like "Blood Draw @ Day 1")
        // Fall back to activity label/name if instance name is missing or just an ID
        let label = activity.label ?? activity.name;
        if (instance.name && !instance.name.match(/^[a-f0-9-]{36}$/i)) {
          // Instance has a human-readable name, use it
          label = instance.name;
        }

        model.nodes.push({
          data: {
            id: nodeId,
            label,
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

  // Mark timing nodes as anchors based on execution model
  // Instead of creating separate anchor nodes, we mark existing encounters as anchors
  if (executionModel?.timeAnchors?.length) {
    const anchorTypes = new Set(executionModel.timeAnchors.map(a => a.anchorType?.toLowerCase()));
    const anchorDays = new Map(executionModel.timeAnchors.map(a => [a.dayValue, a]));
    
    // Update existing timing nodes with anchor info
    for (const node of model.nodes) {
      if (node.data.type === 'timing') {
        // Check if this encounter matches an anchor (by name pattern or day value)
        const label = node.data.label?.toLowerCase() || '';
        const isBaselineAnchor = anchorTypes.has('baseline') && 
          (label.includes('baseline') || label.includes('day 1') || label.includes('screening'));
        const isFirstDoseAnchor = anchorTypes.has('firstdose') && 
          (label.includes('first dose') || label.includes('day 1') || label.includes('treatment'));
        
        if (isBaselineAnchor || isFirstDoseAnchor) {
          node.data.isAnchor = true;
          node.classes = cn(node.classes, 'anchor-timing');
        }
      }
    }
  }

  // Add epoch transition arrows
  for (let i = 0; i < epochs.length - 1; i++) {
    const currentEpoch = epochs[i];
    const nextEpoch = epochs[i + 1];
    
    model.edges.push({
      data: {
        id: `epoch_trans_${currentEpoch.id}_${nextEpoch.id}`,
        source: `epoch_${currentEpoch.id}`,
        target: `epoch_${nextEpoch.id}`,
        type: 'transition',
        label: '→',
      },
      classes: 'epoch-transition',
    });
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
