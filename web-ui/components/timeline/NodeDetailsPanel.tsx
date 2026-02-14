'use client';

import { useState, useRef, useEffect } from 'react';
import {
  X, Anchor, Clock, Activity, Calendar, Info, Link2,
  Pencil, Check, ArrowRight, Undo2, Redo2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useSemanticStore, selectCanUndo, selectCanRedo } from '@/stores/semanticStore';
import { useEditModeStore } from '@/stores/editModeStore';
import { designPath } from '@/lib/semantic/schema';
import type { JsonPatchOp } from '@/lib/semantic/schema';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NodeData {
  id: string;
  label: string;
  type: string;
  usdmRef?: string;
  epochId?: string;
  encounterId?: string;
  activityId?: string;
  timingType?: string;
  timingValue?: string;
  windowLabel?: string;
  isAnchor?: boolean;
  hasWindow?: boolean;
  fromInstanceId?: string;
  toInstanceId?: string;
  parentEncounter?: string;
  [key: string]: unknown;
}

/** Map from USDM entity UUID → human-readable name */
export type EntityNameMap = Map<string, { name: string; type: string; graphNodeId?: string }>;

interface NodeDetailsPanelProps {
  nodeId: string | null;
  nodeData: NodeData | null;
  onClose: () => void;
  /** Navigate to another graph node by its Cytoscape ID */
  onNavigateToNode?: (graphNodeId: string) => void;
  /** ID → name lookup for human-readable cross-references */
  entityNames?: EntityNameMap;
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NODE_ICONS: Record<string, (cls: string) => React.ReactNode> = {
  anchor:   (c) => <Anchor className={cn('h-5 w-5 text-amber-600', c)} />,
  timing:   (c) => <Clock className={cn('h-5 w-5 text-blue-600', c)} />,
  activity: (c) => <Activity className={cn('h-5 w-5 text-green-600', c)} />,
  epoch:    (c) => <Calendar className={cn('h-5 w-5 text-purple-600', c)} />,
  decision: (c) => <Activity className={cn('h-5 w-5 text-amber-600', c)} />,
  window:   (c) => <Clock className={cn('h-5 w-5 text-emerald-600', c)} />,
};

const TYPE_BADGE: Record<string, string> = {
  anchor:   'bg-amber-100 text-amber-800 border-amber-200',
  timing:   'bg-blue-100 text-blue-800 border-blue-200',
  activity: 'bg-green-100 text-green-800 border-green-200',
  epoch:    'bg-purple-100 text-purple-800 border-purple-200',
  decision: 'bg-amber-50 text-amber-800 border-amber-200',
  window:   'bg-emerald-100 text-emerald-800 border-emerald-200',
  instance: 'bg-gray-100 text-gray-800 border-gray-200',
};

/** Map node type → USDM collection name for JSON Patch paths */
const TYPE_TO_COLLECTION: Record<string, string> = {
  timing:   'encounters',
  activity: 'activities',
  epoch:    'epochs',
};

/** Fields that are internal graph IDs — resolve to names */
const ID_FIELDS = new Set([
  'usdmRef', 'epochId', 'encounterId', 'activityId',
  'fromInstanceId', 'toInstanceId', 'parentEncounter',
]);

/** Fields to hide from the "Properties" section */
const HIDDEN_FIELDS = new Set([
  'id', 'label', 'type', 'usdmRef', 'epochId', 'encounterId', 'activityId',
  'fromInstanceId', 'toInstanceId', 'parentEncounter',
  'isAnchor', 'hasWindow', 'windowLabel', 'timingType', 'timingValue',
]);

// ---------------------------------------------------------------------------
// Inline edit field (lightweight, scoped to this panel)
// ---------------------------------------------------------------------------

function InlineEdit({
  value,
  path,
  placeholder,
  multiline,
}: {
  value: string;
  path: string;
  placeholder?: string;
  multiline?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const ref = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
  const { addPatchOp, beginGroup, endGroup } = useSemanticStore();
  const isEditMode = useEditModeStore((s) => s.isEditMode);

  useEffect(() => {
    if (editing && ref.current) {
      ref.current.focus();
      if (ref.current instanceof HTMLInputElement) ref.current.select();
    }
  }, [editing]);

  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  if (!isEditMode) {
    return (
      <span className={cn('text-sm', !value && 'text-muted-foreground italic')}>
        {value || placeholder || 'Not specified'}
      </span>
    );
  }

  if (editing) {
    const save = () => {
      if (draft !== value) {
        beginGroup();
        const op: JsonPatchOp = { op: 'replace', path, value: draft };
        addPatchOp(op);
        endGroup();
      }
      setEditing(false);
    };
    const cancel = () => { setDraft(value); setEditing(false); };
    const Tag = multiline ? 'textarea' : 'input';

    return (
      <div className="flex items-start gap-1">
        <Tag
          ref={ref as any}
          value={draft}
          onChange={(e: any) => setDraft(e.target.value)}
          onKeyDown={(e: React.KeyboardEvent) => {
            if (e.key === 'Enter' && !multiline) { e.preventDefault(); save(); }
            if (e.key === 'Escape') cancel();
          }}
          rows={multiline ? 3 : undefined}
          className="flex-1 min-w-0 px-2 py-1 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <Button variant="outline" size="icon" className="h-7 w-7 shrink-0" onClick={save} title="Save">
          <Check className="h-3.5 w-3.5 text-green-600" />
        </Button>
        <Button variant="outline" size="icon" className="h-7 w-7 shrink-0" onClick={cancel} title="Cancel">
          <X className="h-3.5 w-3.5 text-red-600" />
        </Button>
      </div>
    );
  }

  return (
    <span
      className="group/edit cursor-pointer hover:bg-muted/50 rounded px-1 -mx-1 inline-flex items-center gap-1 text-sm"
      onClick={() => { setDraft(value); setEditing(true); }}
    >
      {value || <span className="text-muted-foreground italic">{placeholder || 'Not specified'}</span>}
      <Pencil className="h-3 w-3 text-muted-foreground opacity-0 group-hover/edit:opacity-100 transition-opacity" />
    </span>
  );
}

// ---------------------------------------------------------------------------
// Cross-reference link (ID → name, clickable)
// ---------------------------------------------------------------------------

function EntityLink({
  id,
  entityNames,
  onNavigateToNode,
  fallbackLabel,
}: {
  id: string;
  entityNames?: EntityNameMap;
  onNavigateToNode?: (graphNodeId: string) => void;
  fallbackLabel?: string;
}) {
  const entry = entityNames?.get(id);
  const displayName = entry?.name ?? fallbackLabel ?? id;
  const typeBadge = entry?.type;
  const graphNodeId = entry?.graphNodeId;
  const canNavigate = Boolean(graphNodeId && onNavigateToNode);

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-xs rounded px-1.5 py-0.5',
        canNavigate
          ? 'bg-blue-50 text-blue-700 hover:bg-blue-100 cursor-pointer transition-colors'
          : 'bg-muted text-foreground',
      )}
      onClick={(e) => {
        e.stopPropagation();
        if (graphNodeId && onNavigateToNode) onNavigateToNode(graphNodeId);
      }}
      title={canNavigate ? `Go to ${displayName}` : id}
    >
      {typeBadge && (
        <Badge variant="outline" className="text-[9px] px-1 py-0 h-4 leading-none border-blue-200">
          {typeBadge}
        </Badge>
      )}
      <span className="font-medium truncate max-w-[140px]">{displayName}</span>
      {canNavigate && <ArrowRight className="h-3 w-3 shrink-0 opacity-60" />}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function NodeDetailsPanel({
  nodeId,
  nodeData,
  onClose,
  onNavigateToNode,
  entityNames,
  className,
}: NodeDetailsPanelProps) {
  const isEditMode = useEditModeStore((s) => s.isEditMode);
  const canUndo = useSemanticStore(selectCanUndo);
  const canRedo = useSemanticStore(selectCanRedo);
  const { undo, redo } = useSemanticStore();

  if (!nodeId || !nodeData) return null;

  const nodeType = nodeData.type;
  const iconFn = NODE_ICONS[nodeType] ?? ((c: string) => <Info className={cn('h-5 w-5 text-gray-600', c)} />);
  const badgeClass = TYPE_BADGE[nodeType] ?? TYPE_BADGE.instance;

  // Determine if this node's USDM entity is editable (has a known collection)
  const collection = TYPE_TO_COLLECTION[nodeType];
  const entityId = nodeData.usdmRef;
  const canEditEntity = Boolean(collection && entityId && isEditMode);

  // Build semantic paths for editable properties
  const namePath = collection && entityId ? designPath(collection, entityId, 'name') : '';
  const descPath = collection && entityId ? designPath(collection, entityId, 'description') : '';

  // Resolve ID-based fields to display as links
  const idRefs: { label: string; id: string }[] = [];
  if (nodeData.epochId) idRefs.push({ label: 'Epoch', id: nodeData.epochId });
  if (nodeData.encounterId && nodeData.encounterId !== nodeData.usdmRef) {
    idRefs.push({ label: 'Encounter', id: nodeData.encounterId });
  }
  if (nodeData.activityId) idRefs.push({ label: 'Activity', id: nodeData.activityId });
  if (nodeData.fromInstanceId) idRefs.push({ label: 'From', id: nodeData.fromInstanceId });
  if (nodeData.toInstanceId) idRefs.push({ label: 'To', id: nodeData.toInstanceId });
  if (nodeData.parentEncounter) idRefs.push({ label: 'Parent', id: nodeData.parentEncounter });

  // Additional display fields (non-hidden, non-ID)
  const extraFields = Object.entries(nodeData).filter(
    ([key, val]) => !HIDDEN_FIELDS.has(key) && val !== undefined && val !== null && val !== '',
  );

  return (
    <Card className={cn('w-80 shadow-lg border-2', className)}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            {iconFn('')}
            <div className="min-w-0">
              {/* Editable node name */}
              {canEditEntity ? (
                <InlineEdit value={nodeData.label} path={namePath} placeholder="Unnamed" />
              ) : (
                <CardTitle className="text-base truncate">{nodeData.label}</CardTitle>
              )}
              <Badge variant="outline" className={cn('mt-1 text-xs', badgeClass)}>
                {nodeType.charAt(0).toUpperCase() + nodeType.slice(1)}
              </Badge>
            </div>
          </div>
          <div className="flex items-center gap-0.5 shrink-0">
            {/* Undo/Redo buttons when in edit mode */}
            {isEditMode && (
              <>
                <Button
                  variant="ghost" size="icon" className="h-7 w-7"
                  disabled={!canUndo} onClick={undo} title="Undo (Ctrl+Z)"
                >
                  <Undo2 className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost" size="icon" className="h-7 w-7"
                  disabled={!canRedo} onClick={redo} title="Redo (Ctrl+Shift+Z)"
                >
                  <Redo2 className="h-3.5 w-3.5" />
                </Button>
              </>
            )}
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0 space-y-3 text-xs">
        {/* Editable description (for encounters/activities/epochs) */}
        {canEditEntity && (
          <div className="space-y-1">
            <span className="text-muted-foreground font-medium">Description</span>
            <InlineEdit
              value={(nodeData as any).description ?? ''}
              path={descPath}
              placeholder="Add description…"
              multiline
            />
          </div>
        )}

        {/* Cross-references — resolved to human-readable names */}
        {idRefs.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-muted-foreground font-medium flex items-center gap-1">
              <Link2 className="h-3 w-3" /> References
            </span>
            <div className="space-y-1">
              {idRefs.map(({ label, id }) => (
                <div key={`${label}-${id}`} className="flex items-center gap-2">
                  <span className="text-muted-foreground w-14 shrink-0">{label}:</span>
                  <EntityLink
                    id={id}
                    entityNames={entityNames}
                    onNavigateToNode={onNavigateToNode}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Visit Window */}
        {nodeData.windowLabel && (
          <div className="p-2 bg-emerald-50 border border-emerald-200 rounded-md">
            <div className="font-medium text-emerald-800">Visit Window</div>
            <div className="text-sm text-emerald-700">{nodeData.windowLabel}</div>
          </div>
        )}

        {/* Timing Info */}
        {nodeData.timingValue && (
          <div className="p-2 bg-blue-50 border border-blue-200 rounded-md">
            <div className="font-medium text-blue-800">Timing</div>
            <div className="text-sm text-blue-700">{nodeData.timingValue}</div>
            {nodeData.timingType && (
              <div className="text-blue-600 mt-1">Type: {nodeData.timingType}</div>
            )}
          </div>
        )}

        {/* Anchor indicator */}
        {nodeData.isAnchor && (
          <div className="p-2 bg-amber-50 border border-amber-200 rounded-md">
            <div className="flex items-center gap-1.5">
              <Anchor className="h-3.5 w-3.5 text-amber-600" />
              <span className="font-medium text-amber-800">Time Anchor</span>
            </div>
            <div className="text-amber-700 mt-1">
              Reference point for timing calculations
            </div>
          </div>
        )}

        {/* Extra properties */}
        {extraFields.length > 0 && (
          <div className="border-t pt-2">
            <span className="text-muted-foreground font-medium">Properties</span>
            <dl className="space-y-1 mt-1">
              {extraFields.slice(0, 8).map(([key, value]) => (
                <div key={key} className="flex justify-between gap-2">
                  <dt className="text-muted-foreground capitalize">
                    {key.replace(/([A-Z])/g, ' $1').trim()}:
                  </dt>
                  <dd className="font-medium truncate max-w-[150px]">
                    {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {/* Edit mode indicator */}
        {isEditMode && canEditEntity && (
          <div className="text-[10px] text-center text-muted-foreground pt-1 border-t">
            Click any field to edit · Changes saved as draft
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default NodeDetailsPanel;
