'use client';

import { useEffect, useRef, useState, forwardRef, useImperativeHandle, useCallback } from 'react';
import cytoscape, { Core, NodeSingular } from 'cytoscape';
import { cytoscapeStyles } from '@/styles/cytoscape-theme';
import { useOverlayStore, selectSnapGrid } from '@/stores/overlayStore';
import type { GraphModel, ValidationError } from '@/lib/adapters/toGraphModel';
import { toCytoscapeElements } from '@/lib/adapters/toGraphModel';
import { cn } from '@/lib/utils';
import { AlertTriangle, Move, ZoomIn } from 'lucide-react';

interface TimelineCanvasProps {
  graphModel: GraphModel;
  onNodeSelect?: (nodeId: string, data: Record<string, unknown>) => void;
  className?: string;
}

export interface TimelineCanvasHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
  exportPNG: () => void;
  center: () => void;
}

export const TimelineCanvas = forwardRef<TimelineCanvasHandle, TimelineCanvasProps>(
  function TimelineCanvas({ graphModel, onNodeSelect, className }, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  
  const snapGrid = useOverlayStore(selectSnapGrid);
  const { updateDraftDiagramNode, lockNode } = useOverlayStore();
  
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [canScroll, setCanScroll] = useState({ x: false, y: false });

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current) return;
    
    // Don't render if validation failed
    if (!graphModel.validation.valid) return;

    const elements = toCytoscapeElements(graphModel);

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: cytoscapeStyles,
      layout: { name: 'preset' }, // Use preset layout (positions from overlay)
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: true,
      minZoom: 0.1,
      maxZoom: 5,
      wheelSensitivity: 0.3, // Smoother zoom
    });

    cyRef.current = cy;

    // Fit to container with padding
    cy.fit(undefined, 50);

    // Track zoom level changes
    cy.on('zoom', () => {
      const zoom = cy.zoom();
      setZoomLevel(zoom);
      // Check if scrolling is needed based on zoom level
      updateScrollState(cy);
    });

    // Track pan state
    cy.on('pan', () => {
      updateScrollState(cy);
    });

    // Track panning gesture
    cy.on('grab', () => setIsPanning(true));
    cy.on('free', () => setIsPanning(false));

    // Helper to check scroll state
    function updateScrollState(cy: Core) {
      const ext = cy.extent();
      const bb = cy.elements().boundingBox();
      const canScrollX = bb.w * cy.zoom() > ext.w;
      const canScrollY = bb.h * cy.zoom() > ext.h;
      setCanScroll({ x: canScrollX, y: canScrollY });
    }

    // Node drag end - snap to grid and update overlay
    cy.on('dragfree', 'node', (evt) => {
      const node = evt.target as NodeSingular;
      
      // Don't move locked nodes
      if (node.hasClass('locked')) {
        return;
      }

      const pos = node.position();
      const snappedPos = {
        x: Math.round(pos.x / snapGrid) * snapGrid,
        y: Math.round(pos.y / snapGrid) * snapGrid,
      };

      // Update node position
      node.position(snappedPos);
      
      // Update overlay store
      updateDraftDiagramNode(node.id(), snappedPos);
    });

    // Double-click to lock/unlock
    cy.on('dbltap', 'node', (evt) => {
      const node = evt.target as NodeSingular;
      const isLocked = node.hasClass('locked');
      
      if (isLocked) {
        node.removeClass('locked');
        node.unlock();
      } else {
        node.addClass('locked');
        node.lock();
      }
      
      lockNode(node.id(), !isLocked);
    });

    // Single click to select
    cy.on('tap', 'node', (evt) => {
      const node = evt.target as NodeSingular;
      setSelectedNode(node.id());
      onNodeSelect?.(node.id(), node.data());
    });

    // Click background to deselect
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
      }
    });

    // Cleanup
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graphModel, snapGrid, updateDraftDiagramNode, lockNode, onNodeSelect]);

  // Update elements when graph model changes
  useEffect(() => {
    if (!cyRef.current || !graphModel.validation.valid) return;
    
    const cy = cyRef.current;
    const elements = toCytoscapeElements(graphModel);
    
    // Update positions for existing nodes
    for (const el of elements) {
      if (el.group === 'nodes' && el.position && el.data.id) {
        const node = cy.getElementById(el.data.id as string);
        if (node.length > 0) {
          node.position(el.position);
          if (el.locked) {
            node.addClass('locked');
            node.lock();
          }
        }
      }
    }
  }, [graphModel]);

  // Show validation errors
  if (!graphModel.validation.valid) {
    return (
      <div className={cn('flex flex-col items-center justify-center h-full bg-muted/30 rounded-lg p-8', className)}>
        <AlertTriangle className="h-12 w-12 text-amber-500 mb-4" />
        <h3 className="text-lg font-semibold mb-2">Validation Errors</h3>
        <p className="text-muted-foreground mb-4 text-center">
          The timeline graph has validation errors and cannot be rendered.
        </p>
        <ValidationErrorList errors={graphModel.validation.errors} />
      </div>
    );
  }

  // Expose methods to parent via ref
  useImperativeHandle(ref, () => ({
    zoomIn: () => {
      if (cyRef.current) {
        cyRef.current.zoom(cyRef.current.zoom() * 1.2);
      }
    },
    zoomOut: () => {
      if (cyRef.current) {
        cyRef.current.zoom(cyRef.current.zoom() / 1.2);
      }
    },
    fit: () => {
      if (cyRef.current) {
        cyRef.current.fit(undefined, 50);
      }
    },
    exportPNG: () => {
      if (cyRef.current) {
        const png = cyRef.current.png({ output: 'blob', bg: 'white', full: true });
        const url = URL.createObjectURL(png as Blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'timeline.png';
        a.click();
        URL.revokeObjectURL(url);
      }
    },
    center: () => {
      if (cyRef.current) {
        cyRef.current.center();
      }
    },
  }), []);

  // Pan handlers for scroll buttons
  const handlePan = useCallback((direction: 'up' | 'down' | 'left' | 'right') => {
    if (!cyRef.current) return;
    const cy = cyRef.current;
    const panAmount = 100;
    const pan = cy.pan();
    
    switch (direction) {
      case 'up': cy.pan({ x: pan.x, y: pan.y + panAmount }); break;
      case 'down': cy.pan({ x: pan.x, y: pan.y - panAmount }); break;
      case 'left': cy.pan({ x: pan.x + panAmount, y: pan.y }); break;
      case 'right': cy.pan({ x: pan.x - panAmount, y: pan.y }); break;
    }
  }, []);

  return (
    <div className={cn('relative w-full h-full', className)}>
      <div 
        ref={containerRef} 
        className="w-full h-full bg-white rounded-lg border"
      />
      
      {/* Scroll/Pan controls - shown when zoomed in */}
      {(canScroll.x || canScroll.y) && (
        <>
          {/* Vertical scroll buttons */}
          {canScroll.y && (
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex flex-col gap-1">
              <button
                onClick={() => handlePan('up')}
                className="p-2 bg-white/90 hover:bg-white border rounded-lg shadow-sm transition-colors"
                title="Pan up"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                </svg>
              </button>
              <button
                onClick={() => handlePan('down')}
                className="p-2 bg-white/90 hover:bg-white border rounded-lg shadow-sm transition-colors"
                title="Pan down"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
          )}
          
          {/* Horizontal scroll buttons */}
          {canScroll.x && (
            <div className="absolute bottom-12 left-1/2 -translate-x-1/2 flex gap-1">
              <button
                onClick={() => handlePan('left')}
                className="p-2 bg-white/90 hover:bg-white border rounded-lg shadow-sm transition-colors"
                title="Pan left"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <button
                onClick={() => handlePan('right')}
                className="p-2 bg-white/90 hover:bg-white border rounded-lg shadow-sm transition-colors"
                title="Pan right"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          )}
        </>
      )}
      
      {/* Zoom level indicator */}
      <div className="absolute top-4 right-4 bg-white/90 backdrop-blur-sm px-3 py-1.5 rounded-lg border shadow-sm text-xs flex items-center gap-2">
        <ZoomIn className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="font-medium">{Math.round(zoomLevel * 100)}%</span>
      </div>
      
      {/* Pan indicator when zoomed in */}
      {(canScroll.x || canScroll.y) && (
        <div className="absolute top-4 left-4 bg-blue-50 border-blue-200 text-blue-700 px-3 py-1.5 rounded-lg border shadow-sm text-xs flex items-center gap-2">
          <Move className="h-3.5 w-3.5" />
          <span>Click & drag to pan</span>
        </div>
      )}
      
      {/* Overlay controls */}
      <div className="absolute bottom-4 left-4 flex items-center gap-2 bg-white/90 backdrop-blur-sm px-3 py-2 rounded-lg border shadow-sm text-xs text-muted-foreground">
        <span>Drag nodes to move</span>
        <span className="text-border">•</span>
        <span>Double-click to lock</span>
        <span className="text-border">•</span>
        <span>Scroll to zoom</span>
      </div>
      
      {/* Snap grid indicator */}
      <div className="absolute bottom-4 right-4 bg-white/90 backdrop-blur-sm px-3 py-2 rounded-lg border shadow-sm text-xs">
        <span className="text-muted-foreground">Snap: </span>
        <span className="font-medium">{snapGrid}px</span>
      </div>
    </div>
  );
});

function ValidationErrorList({ errors }: { errors: ValidationError[] }) {
  return (
    <div className="max-w-md w-full bg-white border rounded-lg p-4 max-h-60 overflow-y-auto">
      <ul className="space-y-2 text-sm">
        {errors.map((error, index) => (
          <li key={index} className="flex items-start gap-2">
            <span className="text-amber-500 mt-0.5">•</span>
            <div>
              <span className="font-medium">{error.type}:</span>{' '}
              <span className="text-muted-foreground">{error.message}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default TimelineCanvas;
