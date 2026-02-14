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
export type NodeType = 'instance' | 'timing' | 'activity' | 'condition' | 'decision' | 'halo' | 'epoch' | 'anchor' | 'window' | 'repetition' | 'swimlane';

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
    // Entity description (for inline editing)
    description?: string;
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
    type: 'timing' | 'activity' | 'condition' | 'sequence' | 'transition' | 'window' | 'decision-branch' | 'decision-default';
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

  // Show all epochs - don't filter based on traversal constraints
  // This ensures the complete study timeline is visible in the graph view
  const epochs = allEpochs;

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
        description: epoch.description,
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
          description: enc.description,
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

  // Generate sequence edges between encounters (only for those with nodes)
  // Filter to encounters whose epoch is in the filtered epoch list to avoid missing endpoint errors
  const encountersWithNodes = encounters.filter(e => e.epochId && epochMap.has(e.epochId));
  
  for (let i = 0; i < encountersWithNodes.length - 1; i++) {
    const current = encountersWithNodes[i];
    const next = encountersWithNodes[i + 1];

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

        // Always prefer activity label/name over instance name
        // Instance names are often generated IDs like "act_1@enc_1" which aren't human-readable
        const label = activity.label ?? activity.name ?? 'Activity';

        model.nodes.push({
          data: {
            id: nodeId,
            label,
            type: 'activity',
            usdmRef: actId,
            encounterId,
            activityId: actId,
            description: activity.description,
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

  // Create dedicated anchor nodes from execution model timeAnchors
  if (executionModel?.timeAnchors?.length) {
    // Build name→position lookup for encounter matching
    const encNodesByLabel = new Map<string, { x: number; y: number; id: string }>();
    for (const node of model.nodes) {
      if (node.data.type === 'timing' && node.position) {
        encNodesByLabel.set((node.data.label || '').toLowerCase(), { ...node.position, id: node.data.id });
      }
    }
    // All encounter x-positions for fallback spreading
    const allEncX = Array.from(encounterPositions.values()).map(p => p.x).sort((a, b) => a - b);
    const graphMinX = allEncX[0] ?? DEFAULT_SPACING.startX;
    const graphMaxX = allEncX[allEncX.length - 1] ?? graphMinX + 400;

    // Anchor-type keywords → encounter name hints
    const anchorKeywords: Record<string, string[]> = {
      baseline:        ['baseline', 'day 1', 'day1'],
      firstdose:       ['first dose', 'day 1', 'day1', 'treatment'],
      day1:            ['day 1', 'day1', 'visit 1'],
      randomization:   ['randomization', 'randomisation', 'random'],
      screening:       ['screening', 'screen'],
      informedconsent: ['informed consent', 'consent', 'ic'],
    };

    executionModel.timeAnchors.forEach((anchor, idx) => {
      const anchorNodeId = `anchor_${anchor.id}`;
      if (nodeIds.has(anchorNodeId)) return;

      // Try to find best encounter to align with
      let bestEncId: string | undefined;
      let bestX = graphMinX + ((graphMaxX - graphMinX) * (idx + 1)) / (executionModel.timeAnchors!.length + 1);

      // 1) Match by anchor type keywords
      const keywords = anchorKeywords[anchor.anchorType?.toLowerCase()] ?? [];
      for (const kw of keywords) {
        for (const [label, pos] of encNodesByLabel) {
          if (label.includes(kw)) {
            bestX = pos.x;
            bestEncId = pos.id;
            break;
          }
        }
        if (bestEncId) break;
      }

      // 2) Also try matching anchor definition text against encounter names
      if (!bestEncId && anchor.definition) {
        const defLower = anchor.definition.toLowerCase();
        for (const [label, pos] of encNodesByLabel) {
          if (defLower.includes(label) || label.includes(defLower.split(' ')[0])) {
            bestX = pos.x;
            bestEncId = pos.id;
            break;
          }
        }
      }

      const position = getNodePosition(anchorNodeId, overlay, {
        x: bestX,
        y: DEFAULT_SPACING.anchorY,
      });

      const label = `⚓ ${anchor.anchorType}${anchor.dayValue != null ? `\nDay ${anchor.dayValue}` : ''}`;

      model.nodes.push({
        data: {
          id: anchorNodeId,
          label,
          type: 'anchor' as NodeType,
          usdmRef: anchor.id,
          isAnchor: true,
        },
        position,
        locked: overlay?.diagram.nodes[anchorNodeId]?.locked,
        classes: 'execution-anchor',
      });
      nodeIds.add(anchorNodeId);

      // Draw a dashed edge from anchor to its aligned encounter
      if (bestEncId) {
        model.edges.push({
          data: {
            id: `anchor_edge_${anchor.id}`,
            source: anchorNodeId,
            target: bestEncId,
            type: 'window',
            label: '',
          },
          classes: 'anchor-edge',
        });
      }
    });
  }

  // ---------------------------------------------------------------
  // Generate ScheduledDecisionInstance (UNS branch) nodes
  // ---------------------------------------------------------------
  for (const timeline of scheduleTimelines) {
    for (const instance of timeline.instances ?? []) {
      if (instance.instanceType !== 'ScheduledDecisionInstance') continue;

      // Find the UNS encounter this SDI controls (from x-unsDecisionInstance extension)
      const unsExt = (instance.extensionAttributes ?? []).find(
        (e) => (e.url ?? '').includes('unsDecisionInstance')
      );
      let unsEncounterId = unsExt?.valueString as string | undefined;

      // The extension may store an alias (e.g. "enc_23") instead of a UUID.
      // Fall back to the first conditionTargetId which is always remapped.
      let unsEncPos = unsEncounterId ? encounterPositions.get(unsEncounterId) : null;
      if (!unsEncPos && instance.conditionAssignments?.length) {
        const firstTarget = instance.conditionAssignments[0].conditionTargetId;
        if (firstTarget) {
          unsEncPos = encounterPositions.get(firstTarget);
          unsEncounterId = firstTarget;
        }
      }
      const defaultX = unsEncPos ? unsEncPos.x : DEFAULT_SPACING.startX;
      const defaultY = unsEncPos ? unsEncPos.y + 80 : DEFAULT_SPACING.encounterY + 80;

      const nodeId = `decision_${instance.id}`;
      const position = getNodePosition(nodeId, overlay, { x: defaultX, y: defaultY });

      model.nodes.push({
        data: {
          id: nodeId,
          label: instance.label ?? instance.name ?? 'UNS Decision',
          type: 'decision',
          usdmRef: instance.id,
          epochId: instance.epochId,
        },
        position,
        locked: overlay?.diagram.nodes[nodeId]?.locked,
        classes: 'decision-node',
      });
      nodeIds.add(nodeId);

      // Edges from decision to branch targets
      for (const ca of instance.conditionAssignments ?? []) {
        const targetId = ca.conditionTargetId;
        if (!targetId) continue;

        const targetNodeId = `enc_${targetId}`;
        if (!nodeIds.has(targetNodeId)) continue;

        const isDefault = targetId === instance.defaultConditionId;
        const edgeId = `decision_edge_${instance.id}_${ca.id ?? targetId}`;

        model.edges.push({
          data: {
            id: edgeId,
            source: nodeId,
            target: targetNodeId,
            type: isDefault ? 'decision-default' : 'decision-branch',
            label: isDefault ? 'default' : ca.condition?.substring(0, 25) || 'event',
          },
          classes: isDefault ? 'decision-default-edge' : 'decision-branch-edge',
        });
      }

      // Edge from the preceding encounter to this decision node
      if (unsEncounterId) {
        const encIdx = encounters.findIndex(e => e.id === unsEncounterId);
        if (encIdx > 0) {
          const prevEnc = encounters[encIdx - 1];
          const prevNodeId = `enc_${prevEnc.id}`;
          if (nodeIds.has(prevNodeId)) {
            model.edges.push({
              data: {
                id: `seq_to_decision_${instance.id}`,
                source: prevNodeId,
                target: nodeId,
                type: 'sequence',
              },
              classes: 'decision-entry-edge',
            });
          }
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
