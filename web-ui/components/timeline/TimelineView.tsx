'use client';

import { useMemo, useCallback, useRef } from 'react';
import { TimelineCanvas, TimelineCanvasHandle } from './TimelineCanvas';
import { TimelineToolbar, TimelineLegend } from './TimelineToolbar';
import { toGraphModel } from '@/lib/adapters/toGraphModel';
import { useProtocolStore, selectStudyDesign } from '@/stores/protocolStore';
import { useOverlayStore, selectDraftPayload } from '@/stores/overlayStore';
import { Card, CardContent } from '@/components/ui/card';

interface TimelineViewProps {
  onNodeSelect?: (nodeId: string, data: Record<string, unknown>) => void;
}

export function TimelineView({ onNodeSelect }: TimelineViewProps) {
  const studyDesign = useProtocolStore(selectStudyDesign);
  const overlayPayload = useOverlayStore(selectDraftPayload);
  const canvasRef = useRef<TimelineCanvasHandle>(null);

  // Build graph model from USDM + overlay
  const graphModel = useMemo(() => {
    return toGraphModel(studyDesign, overlayPayload);
  }, [studyDesign, overlayPayload]);

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

  if (!studyDesign) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No study design data available</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <TimelineToolbar
        nodeCount={stats.nodeCount}
        edgeCount={stats.edgeCount}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onFit={handleFit}
        onResetLayout={handleResetLayout}
        onExportPNG={handleExportPNG}
      />

      {/* Canvas */}
      <Card>
        <CardContent className="p-0">
          <div className="h-[600px]">
            <TimelineCanvas
              ref={canvasRef}
              graphModel={graphModel}
              onNodeSelect={onNodeSelect}
            />
          </div>
        </CardContent>
      </Card>

      {/* Legend */}
      <TimelineLegend className="pt-2" />
    </div>
  );
}

export default TimelineView;
