'use client';

import { useMemo, useCallback, useRef } from 'react';
import { TimelineCanvas } from './TimelineCanvas';
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
  const canvasRef = useRef<any>(null);

  // Build graph model from USDM + overlay
  const graphModel = useMemo(() => {
    return toGraphModel(studyDesign, overlayPayload);
  }, [studyDesign, overlayPayload]);

  // Stats
  const stats = useMemo(() => ({
    nodeCount: graphModel.nodes.length,
    edgeCount: graphModel.edges.length,
  }), [graphModel]);

  // Zoom handlers (would need cy ref exposed from TimelineCanvas)
  const handleZoomIn = useCallback(() => {
    // TODO: Implement zoom via cy ref
  }, []);

  const handleZoomOut = useCallback(() => {
    // TODO: Implement zoom via cy ref
  }, []);

  const handleFit = useCallback(() => {
    // TODO: Implement fit via cy ref
  }, []);

  const handleResetLayout = useCallback(() => {
    // Reset is handled by overlay store
  }, []);

  const handleExportPNG = useCallback(() => {
    // TODO: Implement PNG export via cy ref
    console.log('Export PNG not yet implemented');
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
