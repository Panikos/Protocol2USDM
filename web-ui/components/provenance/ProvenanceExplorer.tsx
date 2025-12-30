'use client';

import { useState, useMemo } from 'react';
import { 
  Search, 
  Filter, 
  ChevronRight, 
  FileText,
  Eye,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ProvenanceStats } from './ProvenanceStats';
import type { ProvenanceData, CellSource } from '@/lib/provenance/types';
import { getProvenanceColor } from '@/lib/provenance/types';
import { cn } from '@/lib/utils';

interface ProvenanceExplorerProps {
  provenance: ProvenanceData | null;
  activities: Array<{ id: string; name: string }>;
  encounters: Array<{ id: string; name: string }>;
  onCellSelect?: (activityId: string, visitId: string) => void;
}

type FilterType = 'all' | 'confirmed' | 'text' | 'vision' | 'orphaned';

export function ProvenanceExplorer({
  provenance,
  activities,
  encounters,
  onCellSelect,
}: ProvenanceExplorerProps) {
  const [searchText, setSearchText] = useState('');
  const [filter, setFilter] = useState<FilterType>('all');
  const [expandedActivities, setExpandedActivities] = useState<Set<string>>(new Set());

  // Build provenance items grouped by activity
  const provenanceItems = useMemo(() => {
    if (!provenance?.activityTimepoints) return [];

    const items: Array<{
      activityId: string;
      activityName: string;
      cells: Array<{
        visitId: string;
        visitName: string;
        source: CellSource;
        footnotes: string[];
      }>;
    }> = [];

    for (const activity of activities) {
      const activityProv = provenance.activityTimepoints[activity.id];
      if (!activityProv) continue;

      const cells: typeof items[0]['cells'] = [];
      
      for (const [visitId, source] of Object.entries(activityProv)) {
        const encounter = encounters.find(e => e.id === visitId);
        const footnotes = provenance.cellFootnotes?.[activity.id]?.[visitId] || [];
        
        cells.push({
          visitId,
          visitName: encounter?.name || visitId,
          source: source as CellSource,
          footnotes,
        });
      }

      if (cells.length > 0) {
        items.push({
          activityId: activity.id,
          activityName: activity.name,
          cells,
        });
      }
    }

    return items;
  }, [provenance, activities, encounters]);

  // Filter items
  const filteredItems = useMemo(() => {
    let items = provenanceItems;

    // Filter by source type
    if (filter !== 'all') {
      items = items.map(item => ({
        ...item,
        cells: item.cells.filter(cell => {
          switch (filter) {
            case 'confirmed': return cell.source === 'both';
            case 'text': return cell.source === 'text';
            case 'vision': return cell.source === 'vision' || cell.source === 'needs_review';
            case 'orphaned': return cell.source === 'none';
            default: return true;
          }
        }),
      })).filter(item => item.cells.length > 0);
    }

    // Filter by search text
    if (searchText) {
      const search = searchText.toLowerCase();
      items = items.filter(item =>
        item.activityName.toLowerCase().includes(search) ||
        item.cells.some(cell => cell.visitName.toLowerCase().includes(search))
      );
    }

    return items;
  }, [provenanceItems, filter, searchText]);

  // Toggle activity expansion
  const toggleActivity = (activityId: string) => {
    setExpandedActivities(prev => {
      const next = new Set(prev);
      if (next.has(activityId)) {
        next.delete(activityId);
      } else {
        next.add(activityId);
      }
      return next;
    });
  };

  // Expand all
  const expandAll = () => {
    setExpandedActivities(new Set(filteredItems.map(i => i.activityId)));
  };

  // Collapse all
  const collapseAll = () => {
    setExpandedActivities(new Set());
  };

  const filterButtons: Array<{ id: FilterType; label: string; icon: React.ReactNode }> = [
    { id: 'all', label: 'All', icon: null },
    { id: 'confirmed', label: 'Confirmed', icon: <CheckCircle className="h-3 w-3 text-green-600" /> },
    { id: 'text', label: 'Text Only', icon: <FileText className="h-3 w-3 text-blue-600" /> },
    { id: 'vision', label: 'Needs Review', icon: <AlertTriangle className="h-3 w-3 text-orange-600" /> },
    { id: 'orphaned', label: 'Orphaned', icon: <Eye className="h-3 w-3 text-red-600" /> },
  ];

  return (
    <div className="space-y-6">
      {/* Stats */}
      <ProvenanceStats provenance={provenance} />

      {/* Controls */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search activities or visits..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                className="w-full pl-9 pr-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            {/* Filter buttons */}
            <div className="flex items-center gap-1 flex-wrap">
              {filterButtons.map((btn) => (
                <Button
                  key={btn.id}
                  variant={filter === btn.id ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFilter(btn.id)}
                  className="gap-1"
                >
                  {btn.icon}
                  {btn.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Expand/collapse */}
          <div className="flex items-center gap-2 mt-3 pt-3 border-t">
            <span className="text-sm text-muted-foreground">
              {filteredItems.length} activities with provenance
            </span>
            <div className="flex-1" />
            <Button variant="ghost" size="sm" onClick={expandAll}>
              Expand All
            </Button>
            <Button variant="ghost" size="sm" onClick={collapseAll}>
              Collapse All
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Provenance items */}
      <div className="space-y-2">
        {filteredItems.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Eye className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-muted-foreground">
                {searchText || filter !== 'all'
                  ? 'No matching provenance data found'
                  : 'No provenance data available'}
              </p>
            </CardContent>
          </Card>
        ) : (
          filteredItems.map((item) => (
            <ProvenanceActivityItem
              key={item.activityId}
              item={item}
              isExpanded={expandedActivities.has(item.activityId)}
              onToggle={() => toggleActivity(item.activityId)}
              onCellClick={onCellSelect}
            />
          ))
        )}
      </div>

      {/* Footnotes */}
      {provenance?.footnotes && provenance.footnotes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">SoA Footnotes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              {provenance.footnotes.map((fn, i) => (
                <div key={i} className="flex gap-2">
                  <span className="font-medium text-blue-600">[{i + 1}]</span>
                  <span className="text-muted-foreground">{fn}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// Activity item with expandable cells
function ProvenanceActivityItem({
  item,
  isExpanded,
  onToggle,
  onCellClick,
}: {
  item: {
    activityId: string;
    activityName: string;
    cells: Array<{
      visitId: string;
      visitName: string;
      source: CellSource;
      footnotes: string[];
    }>;
  };
  isExpanded: boolean;
  onToggle: () => void;
  onCellClick?: (activityId: string, visitId: string) => void;
}) {
  // Count by source type
  const counts = useMemo(() => {
    const c = { confirmed: 0, text: 0, review: 0, orphaned: 0 };
    for (const cell of item.cells) {
      if (cell.source === 'both') c.confirmed++;
      else if (cell.source === 'text') c.text++;
      else if (cell.source === 'vision' || cell.source === 'needs_review') c.review++;
      else c.orphaned++;
    }
    return c;
  }, [item.cells]);

  return (
    <Card>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-muted/50 transition-colors"
      >
        <ChevronRight
          className={cn(
            'h-4 w-4 text-muted-foreground transition-transform',
            isExpanded && 'rotate-90'
          )}
        />
        <div className="flex-1 min-w-0">
          <p className="font-medium truncate">{item.activityName}</p>
          <p className="text-xs text-muted-foreground">
            {item.cells.length} cells tracked
          </p>
        </div>
        
        {/* Mini counts */}
        <div className="flex items-center gap-2 text-xs">
          {counts.confirmed > 0 && (
            <span className="flex items-center gap-1 text-green-600">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              {counts.confirmed}
            </span>
          )}
          {counts.text > 0 && (
            <span className="flex items-center gap-1 text-blue-600">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              {counts.text}
            </span>
          )}
          {counts.review > 0 && (
            <span className="flex items-center gap-1 text-orange-600">
              <span className="w-2 h-2 rounded-full bg-orange-500" />
              {counts.review}
            </span>
          )}
          {counts.orphaned > 0 && (
            <span className="flex items-center gap-1 text-red-600">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              {counts.orphaned}
            </span>
          )}
        </div>
      </button>

      {/* Expanded cells */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t">
          <div className="mt-3 grid gap-2">
            {item.cells.map((cell) => (
              <button
                key={cell.visitId}
                onClick={() => onCellClick?.(item.activityId, cell.visitId)}
                className="flex items-center gap-3 p-2 rounded-md hover:bg-muted text-left text-sm"
              >
                <div
                  className="w-3 h-3 rounded"
                  style={{ backgroundColor: getProvenanceColor(cell.source) }}
                />
                <span className="flex-1">{cell.visitName}</span>
                <span className="text-xs text-muted-foreground capitalize">
                  {cell.source === 'both' ? 'confirmed' : cell.source}
                </span>
                {cell.footnotes.length > 0 && (
                  <span className="text-xs text-blue-600">
                    [{cell.footnotes.join(',')}]
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

export default ProvenanceExplorer;
