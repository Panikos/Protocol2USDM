'use client';

import { useState } from 'react';
import { 
  Download, 
  Filter, 
  Eye, 
  EyeOff,
  RotateCcw,
  Search,
  Keyboard,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ProvenanceLegend } from './ProvenanceCellRenderer';
import { useEditModeStore } from '@/stores/editModeStore';
import { cn } from '@/lib/utils';

interface SoAToolbarProps {
  totalActivities: number;
  totalVisits: number;
  needsReviewCount: number;
  onExportCSV?: () => void;
  onFilterChange?: (filter: FilterOptions) => void;
  onResetLayout?: () => void;
  className?: string;
}

export interface FilterOptions {
  showOnlyNeedsReview: boolean;
  searchText: string;
}

export function SoAToolbar({
  totalActivities,
  totalVisits,
  needsReviewCount,
  onExportCSV,
  onFilterChange,
  onResetLayout,
  className,
}: SoAToolbarProps) {
  const [showOnlyNeedsReview, setShowOnlyNeedsReview] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [showLegend, setShowLegend] = useState(true);
  const isEditMode = useEditModeStore((s) => s.isEditMode);

  const handleFilterToggle = () => {
    const newValue = !showOnlyNeedsReview;
    setShowOnlyNeedsReview(newValue);
    onFilterChange?.({ showOnlyNeedsReview: newValue, searchText });
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchText(value);
    onFilterChange?.({ showOnlyNeedsReview, searchText: value });
  };

  return (
    <div className={cn('space-y-3', className)}>
      {/* Stats and actions row */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        {/* Stats */}
        <div className="flex items-center gap-4 text-sm">
          <span className="text-muted-foreground">
            <strong className="text-foreground">{totalActivities}</strong> activities
          </span>
          <span className="text-muted-foreground">
            <strong className="text-foreground">{totalVisits}</strong> visits
          </span>
          {needsReviewCount > 0 && (
            <span className="text-orange-600">
              <strong>{needsReviewCount}</strong> need review
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search activities..."
              value={searchText}
              onChange={handleSearchChange}
              className="pl-8 pr-3 py-1.5 text-sm border rounded-md w-48 focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          {/* Filter toggle */}
          {needsReviewCount > 0 && (
            <Button
              variant={showOnlyNeedsReview ? 'default' : 'outline'}
              size="sm"
              onClick={handleFilterToggle}
            >
              <Filter className="h-4 w-4 mr-1.5" />
              {showOnlyNeedsReview ? 'Show All' : 'Needs Review'}
            </Button>
          )}

          {/* Legend toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowLegend(!showLegend)}
          >
            {showLegend ? (
              <EyeOff className="h-4 w-4 mr-1.5" />
            ) : (
              <Eye className="h-4 w-4 mr-1.5" />
            )}
            Legend
          </Button>

          {/* Reset layout */}
          <Button
            variant="ghost"
            size="sm"
            onClick={onResetLayout}
          >
            <RotateCcw className="h-4 w-4 mr-1.5" />
            Reset
          </Button>

          {/* Export */}
          <Button
            variant="outline"
            size="sm"
            onClick={onExportCSV}
          >
            <Download className="h-4 w-4 mr-1.5" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Legend row */}
      {showLegend && (
        <ProvenanceLegend className="pt-2 border-t" />
      )}

      {/* Keyboard shortcuts hint — only in edit mode */}
      {isEditMode && (
        <div className="flex items-center gap-4 text-xs text-muted-foreground pt-1 border-t">
          <Keyboard className="h-3.5 w-3.5 shrink-0" />
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px] font-mono">X</kbd> Required</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px] font-mono">O</kbd> Optional</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px] font-mono">-</kbd> N/A</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px] font-mono">Del</kbd> Clear</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px] font-mono">Enter</kbd> Full editor</span>
          <span><kbd className="px-1 py-0.5 bg-muted rounded text-[10px] font-mono">Dbl-click</kbd> Edit cell</span>
        </div>
      )}
    </div>
  );
}

export default SoAToolbar;
