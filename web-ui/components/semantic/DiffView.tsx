'use client';

import { useMemo } from 'react';
import { ArrowRight, Plus, Minus, RefreshCw, Move, Copy, FlaskConical } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useSemanticStore, selectPatchOperations, selectCanUndo } from '@/stores/semanticStore';
import { cn } from '@/lib/utils';
import type { JsonPatchOp } from '@/lib/semantic/schema';

interface DiffViewProps {
  className?: string;
}

/** Friendly label for a JSON Patch path */
function humanizePath(path: string): { entity: string; field: string; fullPath: string } {
  const segments = path.split('/').filter(Boolean);
  // Build a human-friendly label
  // e.g. /study/versions/0/studyDesigns/0/arms/2/name → Arms[2].name
  const parts: string[] = [];
  let field = segments[segments.length - 1] ?? '';

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const next = segments[i + 1];
    if (seg === 'study' || seg === 'versions' || seg === 'studyDesigns') continue;
    if (/^\d+$/.test(seg)) continue; // skip array indices already handled
    if (/^\d+$/.test(next ?? '')) {
      parts.push(`${seg}[${next}]`);
      i++; // skip index
    } else {
      parts.push(seg);
    }
  }

  const entity = parts.length > 1 ? parts.slice(0, -1).join(' › ') : parts[0] ?? 'root';
  return { entity, field, fullPath: path };
}

/** Format a value for display */
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'string') return value.length > 80 ? value.slice(0, 77) + '...' : value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    const json = JSON.stringify(value);
    return json.length > 80 ? json.slice(0, 77) + '...' : json;
  }
  return String(value);
}

/** Icon + color for each op type */
function opMeta(op: string) {
  switch (op) {
    case 'add': return { icon: Plus, color: 'text-green-600', bg: 'bg-green-50', label: 'Add' };
    case 'remove': return { icon: Minus, color: 'text-red-600', bg: 'bg-red-50', label: 'Remove' };
    case 'replace': return { icon: RefreshCw, color: 'text-blue-600', bg: 'bg-blue-50', label: 'Change' };
    case 'move': return { icon: Move, color: 'text-purple-600', bg: 'bg-purple-50', label: 'Move' };
    case 'copy': return { icon: Copy, color: 'text-amber-600', bg: 'bg-amber-50', label: 'Copy' };
    case 'test': return { icon: FlaskConical, color: 'text-gray-600', bg: 'bg-gray-50', label: 'Test' };
    default: return { icon: RefreshCw, color: 'text-gray-600', bg: 'bg-gray-50', label: op };
  }
}

function DiffEntry({ op, index }: { op: JsonPatchOp; index: number }) {
  const { removePatchOp } = useSemanticStore();
  const meta = opMeta(op.op);
  const Icon = meta.icon;
  const { entity, field } = humanizePath(op.path);

  return (
    <div className={cn('flex items-start gap-3 p-3 rounded-md border', meta.bg)}>
      {/* Op icon */}
      <div className={cn('mt-0.5 shrink-0', meta.color)}>
        <Icon className="h-4 w-4" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
            {meta.label}
          </Badge>
          <span className="text-xs text-muted-foreground">{entity}</span>
          <span className="text-xs font-medium">.{field}</span>
        </div>

        {/* Value display */}
        <div className="mt-1 text-sm">
          {op.op === 'remove' ? (
            <span className="text-red-600 line-through">removed</span>
          ) : op.op === 'move' || op.op === 'copy' ? (
            <span className="text-muted-foreground">
              from <code className="text-xs bg-muted px-1 rounded">{op.from}</code>
            </span>
          ) : 'value' in op ? (
            <span className={cn(
              op.op === 'add' ? 'text-green-700' : 'text-blue-700'
            )}>
              {formatValue(op.value)}
            </span>
          ) : null}
        </div>

        {/* Path detail */}
        <code className="text-[10px] text-muted-foreground mt-1 block truncate">
          {op.path}
        </code>
      </div>

      {/* Remove single op */}
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 shrink-0 opacity-50 hover:opacity-100 text-destructive"
        onClick={() => removePatchOp(index)}
        title="Remove this change"
      >
        <Minus className="h-3 w-3" />
      </Button>
    </div>
  );
}

export function DiffView({ className }: DiffViewProps) {
  const patch = useSemanticStore(selectPatchOperations);
  const { clearPatch, undo } = useSemanticStore();
  const canUndo = useSemanticStore(selectCanUndo);

  // Group ops by entity path for summary
  const summary = useMemo(() => {
    const counts = { add: 0, remove: 0, replace: 0, move: 0, copy: 0, test: 0 };
    for (const op of patch) {
      counts[op.op as keyof typeof counts] = (counts[op.op as keyof typeof counts] ?? 0) + 1;
    }
    return counts;
  }, [patch]);

  if (patch.length === 0) {
    return (
      <Card className={className}>
        <CardContent className="py-8 text-center">
          <p className="text-muted-foreground text-sm">No pending changes</p>
          <p className="text-muted-foreground text-xs mt-1">
            Toggle Edit Mode and modify fields to see changes here
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-base">
          <span className="flex items-center gap-2">
            Pending Changes
            <Badge variant="secondary">{patch.length}</Badge>
          </span>
          <div className="flex items-center gap-1">
            {canUndo && (
              <Button variant="ghost" size="sm" onClick={undo}>
                Undo Last
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={clearPatch} className="text-destructive">
              Clear All
            </Button>
          </div>
        </CardTitle>

        {/* Summary badges */}
        <div className="flex gap-2 mt-1">
          {summary.add > 0 && (
            <Badge variant="outline" className="text-green-600 border-green-200 bg-green-50">
              +{summary.add} added
            </Badge>
          )}
          {summary.replace > 0 && (
            <Badge variant="outline" className="text-blue-600 border-blue-200 bg-blue-50">
              {summary.replace} changed
            </Badge>
          )}
          {summary.remove > 0 && (
            <Badge variant="outline" className="text-red-600 border-red-200 bg-red-50">
              -{summary.remove} removed
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
          {patch.map((op, i) => (
            <DiffEntry key={i} op={op} index={i} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default DiffView;
