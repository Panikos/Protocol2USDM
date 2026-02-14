'use client';

import { useMemo, useCallback, useRef, useState } from 'react';
import { TimelineCanvas, TimelineCanvasHandle, LayoutName } from './TimelineCanvas';
import { TimelineToolbar, TimelineLegend } from './TimelineToolbar';
import { toGraphModel, ExecutionModelData } from '@/lib/adapters/toGraphModel';
import { useOverlayStore, selectDraftPayload } from '@/stores/overlayStore';
import { usePatchedStudyDesign } from '@/hooks/usePatchedUsdm';
import { Card, CardContent } from '@/components/ui/card';
import { X, Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { NodeDetailsPanel } from './NodeDetailsPanel';
import type { EntityNameMap } from './NodeDetailsPanel';

interface TimelineViewProps {
  onNodeSelect?: (nodeId: string, data: Record<string, unknown>) => void;
  executionModel?: ExecutionModelData | null;
}

export function TimelineView({ onNodeSelect, executionModel }: TimelineViewProps) {
  // Use patched study design to show draft changes
  const studyDesign = usePatchedStudyDesign();
  const overlayPayload = useOverlayStore(selectDraftPayload);
  const canvasRef = useRef<TimelineCanvasHandle>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedNode, setSelectedNode] = useState<{ id: string; data: Record<string, unknown> } | null>(null);
  const [activeLayout, setActiveLayout] = useState<LayoutName>('preset');

  // Build graph model from USDM + overlay + execution model
  const graphModel = useMemo(() => {
    return toGraphModel(studyDesign, overlayPayload, executionModel);
  }, [studyDesign, overlayPayload, executionModel]);

  // Build entity name map: USDM UUID → {name, type, graphNodeId}
  const entityNames: EntityNameMap = useMemo(() => {
    const map: EntityNameMap = new Map();
    if (!studyDesign) return map;
    const sd = studyDesign as Record<string, unknown>;

    // Epochs
    for (const e of (sd.epochs as any[] ?? [])) {
      map.set(e.id, { name: e.name || 'Unnamed Epoch', type: 'Epoch', graphNodeId: `epoch_${e.id}` });
    }
    // Encounters
    for (const e of (sd.encounters as any[] ?? [])) {
      map.set(e.id, { name: e.name || 'Unnamed Encounter', type: 'Encounter', graphNodeId: `enc_${e.id}` });
    }
    // Activities
    for (const a of (sd.activities as any[] ?? [])) {
      map.set(a.id, { name: a.name || 'Unnamed Activity', type: 'Activity', graphNodeId: `act_${a.id}` });
    }
    // Arms
    for (const a of (sd.arms as any[] ?? [])) {
      map.set(a.id, { name: a.name || 'Unnamed Arm', type: 'Arm' });
    }
    // Timings (from schedule timelines)
    for (const tl of (sd.scheduleTimelines as any[] ?? [])) {
      for (const t of (tl.timings ?? [])) {
        map.set(t.id, { name: t.name || t.label || 'Timing', type: 'Timing', graphNodeId: `timing_${t.id}` });
      }
      for (const inst of (tl.instances ?? [])) {
        map.set(inst.id, { name: inst.name || inst.instanceType || 'Instance', type: inst.instanceType || 'Instance' });
      }
    }
    return map;
  }, [studyDesign]);

  // Stats
  const stats = useMemo(() => ({
    nodeCount: graphModel.nodes.length,
    edgeCount: graphModel.edges.length,
  }), [graphModel]);

  // Zoom handlers - call methods on canvas ref
  const handleZoomIn = useCallback(() => {
    canvasRef.current?.zoomIn();
  }, []);

  const handleZoomOut = useCallback(() => {
    canvasRef.current?.zoomOut();
  }, []);

  const handleFit = useCallback(() => {
    canvasRef.current?.fit();
  }, []);

  const handleResetLayout = useCallback(() => {
    // Reset is handled by overlay store, then fit
    canvasRef.current?.fit();
  }, []);

  const handleExportPNG = useCallback(() => {
    canvasRef.current?.exportPNG();
  }, []);

  const handleLayoutChange = useCallback((layout: LayoutName) => {
    setActiveLayout(layout);
    canvasRef.current?.runLayout(layout);
  }, []);

  const toggleFullscreen = useCallback(() => {
    setIsFullscreen(prev => !prev);
  }, []);

  const handleNodeSelect = useCallback((nodeId: string, data: Record<string, unknown>) => {
    setSelectedNode({ id: nodeId, data });
    onNodeSelect?.(nodeId, data);
  }, [onNodeSelect]);

  const handleCloseDetails = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Navigate to a different graph node (from cross-reference click)
  const handleNavigateToNode = useCallback((graphNodeId: string) => {
    canvasRef.current?.selectNode(graphNodeId);
  }, []);

  if (!studyDesign) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No study design data available</p>
        </CardContent>
      </Card>
    );
  }

  // Fullscreen container
  const containerClasses = isFullscreen
    ? 'fixed inset-0 z-50 bg-white flex flex-col'
    : 'space-y-4';

  const canvasHeight = isFullscreen ? 'flex-1' : 'h-[600px]';

  return (
    <div className={containerClasses}>
      {/* Fullscreen header */}
      {isFullscreen && (
        <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
          <h2 className="text-lg font-semibold">Timeline Graph View</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleFullscreen}
            className="gap-1.5"
          >
            <X className="h-4 w-4" />
            Exit Fullscreen
          </Button>
        </div>
      )}

      {/* Toolbar */}
      <div className={cn(isFullscreen ? 'px-4 py-2 border-b' : '')}>
        <TimelineToolbar
          nodeCount={stats.nodeCount}
          edgeCount={stats.edgeCount}
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onFit={handleFit}
          onResetLayout={handleResetLayout}
          onExportPNG={handleExportPNG}
          onToggleFullscreen={toggleFullscreen}
          onLayoutChange={handleLayoutChange}
          activeLayout={activeLayout}
          isFullscreen={isFullscreen}
        />
      </div>

      {/* Canvas */}
      <Card className={cn(isFullscreen ? 'flex-1 rounded-none border-0' : '', 'relative')}>
        <CardContent className="p-0 h-full relative">
          <div className={cn(canvasHeight, 'relative')}>
            <TimelineCanvas
              ref={canvasRef}
              graphModel={graphModel}
              onNodeSelect={handleNodeSelect}
            />
          </div>
          
          {/* Node Details Panel - positioned outside canvas */}
          {selectedNode && (
            <div className="absolute top-4 right-4 z-20">
              <NodeDetailsPanel
                nodeId={selectedNode.id}
                nodeData={selectedNode.data as any}
                onClose={handleCloseDetails}
                onNavigateToNode={handleNavigateToNode}
                entityNames={entityNames}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Legend */}
      {!isFullscreen && <TimelineLegend className="pt-2" />}
      {isFullscreen && (
        <div className="px-4 py-2 border-t bg-gray-50">
          <TimelineLegend />
        </div>
      )}
    </div>
  );
}

export default TimelineView;
