'use client';

import { useState } from 'react';
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize, 
  Minimize,
  Lock, 
  Unlock,
  RotateCcw,
  Grid,
  Download,
  Fullscreen,
  Anchor,
  Clock,
  Activity,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useOverlayStore, selectSnapGrid } from '@/stores/overlayStore';
import { cn } from '@/lib/utils';

interface TimelineToolbarProps {
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onFit?: () => void;
  onResetLayout?: () => void;
  onExportPNG?: () => void;
  onToggleFullscreen?: () => void;
  isFullscreen?: boolean;
  nodeCount: number;
  edgeCount: number;
  className?: string;
}

export function TimelineToolbar({
  onZoomIn,
  onZoomOut,
  onFit,
  onResetLayout,
  onExportPNG,
  onToggleFullscreen,
  isFullscreen,
  nodeCount,
  edgeCount,
  className,
}: TimelineToolbarProps) {
  const snapGrid = useOverlayStore(selectSnapGrid);
  const { setSnapGrid, resetToPublished } = useOverlayStore();
  const [showSnapOptions, setShowSnapOptions] = useState(false);

  const snapOptions = [5, 10, 20, 50];

  return (
    <div className={cn('flex items-center justify-between flex-wrap gap-3', className)}>
      {/* Stats */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-muted-foreground">
          <strong className="text-foreground">{nodeCount}</strong> nodes
        </span>
        <span className="text-muted-foreground">
          <strong className="text-foreground">{edgeCount}</strong> edges
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {/* Zoom controls */}
        <div className="flex items-center border rounded-md">
          <Button
            variant="ghost"
            size="sm"
            onClick={onZoomOut}
            className="rounded-r-none border-r"
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onZoomIn}
            className="rounded-none border-r"
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onFit}
            className="rounded-l-none"
          >
            <Maximize className="h-4 w-4" />
          </Button>
        </div>

        {/* Snap grid selector */}
        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSnapOptions(!showSnapOptions)}
            className="gap-1.5"
          >
            <Grid className="h-4 w-4" />
            {snapGrid}px
          </Button>
          
          {showSnapOptions && (
            <div className="absolute top-full mt-1 right-0 bg-white border rounded-md shadow-lg z-10 py-1">
              {snapOptions.map((value) => (
                <button
                  key={value}
                  onClick={() => {
                    setSnapGrid(value);
                    setShowSnapOptions(false);
                  }}
                  className={cn(
                    'w-full px-4 py-1.5 text-sm text-left hover:bg-muted',
                    snapGrid === value && 'bg-muted font-medium'
                  )}
                >
                  {value}px
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Reset layout */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            resetToPublished();
            onResetLayout?.();
          }}
        >
          <RotateCcw className="h-4 w-4 mr-1.5" />
          Reset
        </Button>

        {/* Export */}
        <Button
          variant="outline"
          size="sm"
          onClick={onExportPNG}
        >
          <Download className="h-4 w-4 mr-1.5" />
          Export PNG
        </Button>

        {/* Fullscreen toggle */}
        <Button
          variant="default"
          size="sm"
          onClick={onToggleFullscreen}
          className="gap-1.5"
        >
          {isFullscreen ? (
            <>
              <Minimize className="h-4 w-4" />
              Exit
            </>
          ) : (
            <>
              <Fullscreen className="h-4 w-4" />
              Fullscreen
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

// Node type legend
export function TimelineLegend({ className }: { className?: string }) {
  const nodeItems = [
    { color: 'bg-blue-100 border-blue-500', label: 'Epoch' },
    { color: 'bg-white border-gray-700', label: 'Encounter', shape: 'rounded-full' },
    { color: 'bg-white border-green-500', label: 'Activity' },
    { color: 'bg-white border-[#003366] border-2', label: 'Timing', shape: 'rounded-full' },
    { color: 'bg-amber-100 border-amber-600 border-2', label: 'Anchor ⚓', shape: 'rounded-full' },
    { color: 'bg-amber-50 border-amber-600 border-dashed', label: 'UNS Decision', shape: 'rotate-45' },
  ];

  const edgeItems = [
    { color: 'bg-gray-500', label: 'Sequence', style: 'solid' },
    { color: 'bg-green-500', label: 'Activity Link', style: 'dashed' },
    { color: 'bg-slate-500', label: 'Epoch Transition', style: 'solid' },
    { color: 'bg-amber-400', label: 'UNS Branch', style: 'dashed' },
  ];

  return (
    <div className={cn('flex flex-wrap items-center gap-6 text-sm', className)}>
      {/* Nodes */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-medium text-muted-foreground">Nodes:</span>
        {nodeItems.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <div 
              className={cn(
                'w-4 h-4 border-2',
                item.color,
                item.shape || 'rounded'
              )} 
            />
            <span className="text-muted-foreground">{item.label}</span>
          </div>
        ))}
      </div>

      {/* Divider */}
      <div className="h-4 w-px bg-border" />

      {/* Edges */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-medium text-muted-foreground">Edges:</span>
        {edgeItems.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <div className="flex items-center w-6">
              <div 
                className={cn(
                  'h-0.5 w-full',
                  item.color,
                  item.style === 'dashed' && 'border-t-2 border-dashed bg-transparent'
                )} 
              />
              <div 
                className={cn(
                  'w-0 h-0 border-t-[4px] border-t-transparent border-b-[4px] border-b-transparent border-l-[6px]',
                  item.color.replace('bg-', 'border-l-')
                )}
              />
            </div>
            <span className="text-muted-foreground">{item.label}</span>
          </div>
        ))}
      </div>

      {/* Divider */}
      <div className="h-4 w-px bg-border" />

      {/* Controls */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <Lock className="h-3.5 w-3.5 text-blue-500" />
          <span className="text-muted-foreground">Locked Node</span>
        </div>
      </div>
    </div>
  );
}

export default TimelineToolbar;
