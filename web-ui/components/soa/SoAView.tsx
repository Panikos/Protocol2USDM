'use client';

import { useState, useMemo, useCallback } from 'react';
import { SoAGrid } from './SoAGrid';
import { SoAToolbar, FilterOptions } from './SoAToolbar';
import { FootnotePanel } from './FootnotePanel';
import { toSoATableModel, SoACell, cellKey } from '@/lib/adapters/toSoATableModel';
import { useProtocolStore, selectStudyDesign } from '@/stores/protocolStore';
import { useOverlayStore, selectDraftPayload } from '@/stores/overlayStore';
import type { ProvenanceData } from '@/lib/provenance/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface SoAViewProps {
  provenance: ProvenanceData | null;
}

export function SoAView({ provenance }: SoAViewProps) {
  const studyDesign = useProtocolStore(selectStudyDesign);
  const overlayPayload = useOverlayStore(selectDraftPayload);
  const { resetToPublished } = useOverlayStore();

  const [filter, setFilter] = useState<FilterOptions>({
    showOnlyNeedsReview: false,
    searchText: '',
  });
  const [selectedCell, setSelectedCell] = useState<{
    activityId: string;
    visitId: string;
    cell: SoACell | undefined;
  } | null>(null);

  // Build table model from USDM + overlay + provenance
  const tableModel = useMemo(() => {
    return toSoATableModel(studyDesign, overlayPayload, provenance);
  }, [studyDesign, overlayPayload, provenance]);

  // Calculate stats
  const stats = useMemo(() => {
    let needsReviewCount = 0;
    for (const cell of tableModel.cells.values()) {
      if (cell.provenance.needsReview && cell.mark) {
        needsReviewCount++;
      }
    }
    return {
      totalActivities: tableModel.rows.length,
      totalVisits: tableModel.columns.length,
      needsReviewCount,
    };
  }, [tableModel]);

  // Filter model based on filter options
  const filteredModel = useMemo(() => {
    if (!filter.showOnlyNeedsReview && !filter.searchText) {
      return tableModel;
    }

    let filteredRows = tableModel.rows;

    // Filter by needs review
    if (filter.showOnlyNeedsReview) {
      const rowsWithReview = new Set<string>();
      for (const [key, cell] of tableModel.cells.entries()) {
        if (cell.provenance.needsReview && cell.mark) {
          const [activityId] = key.split('|');
          rowsWithReview.add(activityId);
        }
      }
      filteredRows = filteredRows.filter((row) => rowsWithReview.has(row.id));
    }

    // Filter by search text
    if (filter.searchText) {
      const searchLower = filter.searchText.toLowerCase();
      filteredRows = filteredRows.filter(
        (row) =>
          row.name.toLowerCase().includes(searchLower) ||
          row.groupName?.toLowerCase().includes(searchLower)
      );
    }

    return {
      ...tableModel,
      rows: filteredRows,
    };
  }, [tableModel, filter]);

  // Handle cell click
  const handleCellClick = useCallback(
    (activityId: string, visitId: string, cell: SoACell | undefined) => {
      setSelectedCell({ activityId, visitId, cell });
    },
    []
  );

  // Export to CSV
  const handleExportCSV = useCallback(() => {
    const headers = [
      'Category',
      'Activity',
      ...tableModel.columns.map((col) => `${col.epochName} - ${col.name}`),
    ];

    const rows = tableModel.rows.map((row) => {
      const values = [
        row.groupName || '',
        row.name,
        ...tableModel.columns.map((col) => {
          const cell = tableModel.cells.get(cellKey(row.id, col.id));
          return cell?.mark || '';
        }),
      ];
      return values.map((v) => `"${v}"`).join(',');
    });

    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'soa_export.csv';
    a.click();
    URL.revokeObjectURL(url);
  }, [tableModel]);

  // Get footnotes from provenance
  const footnotes = provenance?.footnotes || [];

  // Get selected cell footnotes
  const selectedFootnoteRefs = selectedCell?.cell?.footnoteRefs;

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
      <SoAToolbar
        totalActivities={stats.totalActivities}
        totalVisits={stats.totalVisits}
        needsReviewCount={stats.needsReviewCount}
        onExportCSV={handleExportCSV}
        onFilterChange={setFilter}
        onResetLayout={resetToPublished}
      />

      {/* Grid */}
      <Card>
        <CardContent className="p-0">
          <div className="h-[600px]">
            <SoAGrid
              model={filteredModel}
              onCellClick={handleCellClick}
            />
          </div>
        </CardContent>
      </Card>

      {/* Footnotes */}
      {footnotes.length > 0 && (
        <FootnotePanel
          footnotes={footnotes}
          selectedFootnoteRefs={selectedFootnoteRefs}
        />
      )}

      {/* Selected cell info */}
      {selectedCell && selectedCell.cell && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm">Selected Cell</CardTitle>
          </CardHeader>
          <CardContent className="py-3 text-sm">
            <dl className="grid grid-cols-2 gap-2">
              <dt className="text-muted-foreground">Activity:</dt>
              <dd>{tableModel.rows.find((r) => r.id === selectedCell.activityId)?.name}</dd>
              <dt className="text-muted-foreground">Visit:</dt>
              <dd>{tableModel.columns.find((c) => c.id === selectedCell.visitId)?.name}</dd>
              <dt className="text-muted-foreground">Mark:</dt>
              <dd>{selectedCell.cell.mark || '(empty)'}</dd>
              <dt className="text-muted-foreground">Provenance:</dt>
              <dd className="capitalize">{selectedCell.cell.provenance.source}</dd>
            </dl>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default SoAView;
