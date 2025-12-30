'use client';

import { useState } from 'react';
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize, 
  Lock, 
  Unlock,
  RotateCcw,
  Grid,
  Download,
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
    { color: 'bg-white border-[#003366] border-3', label: 'Anchor (⚓)', shape: 'rounded-full' },
  ];

  return (
    <div className={cn('flex flex-wrap items-center gap-4 text-sm', className)}>
      <span className="font-medium text-muted-foreground">Node Types:</span>
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
      <div className="flex items-center gap-1.5">
        <Lock className="h-3.5 w-3.5 text-blue-500" />
        <span className="text-muted-foreground">Locked</span>
      </div>
    </div>
  );
}

export default TimelineToolbar;
