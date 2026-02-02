'use client';

import { X, Anchor, Clock, Activity, Calendar, Info, Link2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

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
  [key: string]: unknown;
}

interface NodeDetailsPanelProps {
  nodeId: string | null;
  nodeData: NodeData | null;
  onClose: () => void;
  className?: string;
}

export function NodeDetailsPanel({ nodeId, nodeData, onClose, className }: NodeDetailsPanelProps) {
  if (!nodeId || !nodeData) return null;

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'anchor': return <Anchor className="h-5 w-5 text-amber-600" />;
      case 'timing': return <Clock className="h-5 w-5 text-blue-600" />;
      case 'activity': return <Activity className="h-5 w-5 text-green-600" />;
      case 'epoch': return <Calendar className="h-5 w-5 text-purple-600" />;
      case 'window': return <Clock className="h-5 w-5 text-emerald-600" />;
      default: return <Info className="h-5 w-5 text-gray-600" />;
    }
  };

  const getNodeTypeBadge = (type: string) => {
    const variants: Record<string, string> = {
      anchor: 'bg-amber-100 text-amber-800 border-amber-200',
      timing: 'bg-blue-100 text-blue-800 border-blue-200',
      activity: 'bg-green-100 text-green-800 border-green-200',
      epoch: 'bg-purple-100 text-purple-800 border-purple-200',
      window: 'bg-emerald-100 text-emerald-800 border-emerald-200',
      instance: 'bg-gray-100 text-gray-800 border-gray-200',
    };
    return variants[type] || variants.instance;
  };

  // Extract key-value pairs for display, excluding internal fields
  const displayFields = Object.entries(nodeData).filter(([key]) => 
    !['id', 'label', 'type'].includes(key) && 
    nodeData[key] !== undefined && 
    nodeData[key] !== null &&
    nodeData[key] !== ''
  );

  return (
    <Card className={cn('w-80 shadow-lg', className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            {getNodeIcon(nodeData.type)}
            <div>
              <CardTitle className="text-base">{nodeData.label}</CardTitle>
              <Badge variant="outline" className={cn('mt-1 text-xs', getNodeTypeBadge(nodeData.type))}>
                {nodeData.type.charAt(0).toUpperCase() + nodeData.type.slice(1)}
              </Badge>
            </div>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-3">
          {/* Node ID */}
          <div className="text-xs">
            <span className="text-muted-foreground">Node ID: </span>
            <code className="bg-muted px-1 py-0.5 rounded text-[10px]">{nodeId}</code>
          </div>

          {/* USDM Reference */}
          {nodeData.usdmRef && (
            <div className="flex items-center gap-1.5 text-xs">
              <Link2 className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-muted-foreground">USDM Ref: </span>
              <code className="bg-muted px-1 py-0.5 rounded text-[10px] truncate max-w-[150px]">
                {nodeData.usdmRef}
              </code>
            </div>
          )}

          {/* Window Label */}
          {nodeData.windowLabel && (
            <div className="p-2 bg-emerald-50 border border-emerald-200 rounded-md">
              <div className="text-xs font-medium text-emerald-800">Visit Window</div>
              <div className="text-sm text-emerald-700">{nodeData.windowLabel}</div>
            </div>
          )}

          {/* Timing Info */}
          {nodeData.timingValue && (
            <div className="p-2 bg-blue-50 border border-blue-200 rounded-md">
              <div className="text-xs font-medium text-blue-800">Timing</div>
              <div className="text-sm text-blue-700">{nodeData.timingValue}</div>
              {nodeData.timingType && (
                <div className="text-xs text-blue-600 mt-1">Type: {nodeData.timingType}</div>
              )}
            </div>
          )}

          {/* Anchor indicator */}
          {nodeData.isAnchor && (
            <div className="p-2 bg-amber-50 border border-amber-200 rounded-md">
              <div className="flex items-center gap-1.5">
                <Anchor className="h-3.5 w-3.5 text-amber-600" />
                <span className="text-xs font-medium text-amber-800">Time Anchor</span>
              </div>
              <div className="text-xs text-amber-700 mt-1">
                This is a reference point for timing calculations
              </div>
            </div>
          )}

          {/* Additional fields */}
          {displayFields.length > 0 && (
            <div className="border-t pt-3 mt-3">
              <div className="text-xs font-medium text-muted-foreground mb-2">Properties</div>
              <dl className="space-y-1.5 text-xs">
                {displayFields.slice(0, 8).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <dt className="text-muted-foreground capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}:</dt>
                    <dd className="font-medium truncate max-w-[150px]">
                      {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default NodeDetailsPanel;
