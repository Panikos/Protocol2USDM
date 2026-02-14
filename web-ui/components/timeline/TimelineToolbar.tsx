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
  LayoutGrid,
  Circle,
  GitBranch,
  Waypoints,
  Orbit,
  MapPin,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useOverlayStore, selectSnapGrid } from '@/stores/overlayStore';
import { cn } from '@/lib/utils';

import type { LayoutName } from './TimelineCanvas';

const LAYOUT_OPTIONS: { value: LayoutName; label: string; description: string }[] = [
  { value: 'preset',       label: 'Saved',        description: 'Saved node positions' },
  { value: 'grid',         label: 'Grid',         description: 'Even grid arrangement' },
  { value: 'circle',       label: 'Circle',       description: 'Nodes in a circle' },
  { value: 'concentric',   label: 'Concentric',   description: 'Rings by connectivity' },
  { value: 'breadthfirst', label: 'Hierarchy',    description: 'Top-down tree layout' },
  { value: 'cose',         label: 'Force',        description: 'Physics simulation' },
];

function LayoutIcon({ name, className }: { name: LayoutName; className?: string }) {
  switch (name) {
    case 'preset':       return <MapPin className={className} />;
    case 'grid':         return <LayoutGrid className={className} />;
    case 'circle':       return <Circle className={className} />;
    case 'concentric':   return <Orbit className={className} />;
    case 'breadthfirst': return <GitBranch className={className} />;
    case 'cose':         return <Waypoints className={className} />;
    default:             return <LayoutGrid className={className} />;
  }
}

interface TimelineToolbarProps {
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onFit?: () => void;
  onResetLayout?: () => void;
  onExportPNG?: () => void;
  onToggleFullscreen?: () => void;
  onLayoutChange?: (layout: LayoutName) => void;
  isFullscreen?: boolean;
  activeLayout?: LayoutName;
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
  onLayoutChange,
  isFullscreen,
  activeLayout = 'preset',
  nodeCount,
  edgeCount,
  className,
}: TimelineToolbarProps) {
  const snapGrid = useOverlayStore(selectSnapGrid);
  const { setSnapGrid, resetToPublished } = useOverlayStore();
  const [showSnapOptions, setShowSnapOptions] = useState(false);
  const [showLayoutOptions, setShowLayoutOptions] = useState(false);
  const activeOpt = LAYOUT_OPTIONS.find(l => l.value === activeLayout) ?? LAYOUT_OPTIONS[0];

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
      <div className="flex items-center flex-wrap gap-2">
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

        {/* Layout selector */}
        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            onClick={() => { setShowLayoutOptions(!showLayoutOptions); setShowSnapOptions(false); }}
            className="gap-1.5"
            title="Change graph layout"
          >
            <LayoutIcon name={activeLayout} className="h-4 w-4" />
            <span>{activeOpt.label}</span>
          </Button>

          {showLayoutOptions && (
            <div className="absolute top-full mt-1 right-0 bg-white dark:bg-gray-900 border rounded-md shadow-lg z-20 py-1 min-w-[180px]">
              {LAYOUT_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => {
                    onLayoutChange?.(opt.value);
                    setShowLayoutOptions(false);
                  }}
                  className={cn(
                    'w-full px-3 py-2 text-sm text-left hover:bg-muted flex items-center gap-2',
                    activeLayout === opt.value && 'bg-muted font-medium'
                  )}
                >
                  <LayoutIcon name={opt.value} className="h-4 w-4" />
                  <div>
                    <div className="font-medium">{opt.label}</div>
                    <div className="text-xs text-muted-foreground">{opt.description}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Snap grid selector */}
        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            onClick={() => { setShowSnapOptions(!showSnapOptions); setShowLayoutOptions(false); }}
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
