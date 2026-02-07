'use client';

import { useState, useMemo, useCallback } from 'react';
import { SoAGrid } from './SoAGrid';
import { SoAToolbar, FilterOptions } from './SoAToolbar';
import { FootnotePanel } from './FootnotePanel';
import { toSoATableModel, SoACell, cellKey } from '@/lib/adapters/toSoATableModel';
import { useOverlayStore, selectDraftPayload } from '@/stores/overlayStore';
import { useSoAEditStore } from '@/stores/soaEditStore';
import { useProtocolStore } from '@/stores/protocolStore';
import { usePatchedStudyDesign } from '@/hooks/usePatchedUsdm';
import type { ProvenanceData } from '@/lib/provenance/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle } from 'lucide-react';

interface SoAViewProps {
  provenance: ProvenanceData | null;
}

export function SoAView({ provenance }: SoAViewProps) {
  // Use patched study design to show draft changes
  const studyDesign = usePatchedStudyDesign();
  const overlayPayload = useOverlayStore(selectDraftPayload);
  const { resetToPublished } = useOverlayStore();
  const { lastError } = useSoAEditStore();
  // Get revision to force SoAGrid re-render when USDM is reloaded
  const revision = useProtocolStore(state => state.revision);

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

  // Get footnotes - prefer authoritative SoA footnotes from USDM extension, fall back to provenance
  const { footnotes, footnoteExtIndex } = useMemo(() => {
    // First check for authoritative SoA footnotes in studyDesign.extensionAttributes
    const extensions = studyDesign?.extensionAttributes as Array<{ url?: string; valueString?: string }> | undefined;
    if (extensions && Array.isArray(extensions)) {
      for (let i = 0; i < extensions.length; i++) {
        const ext = extensions[i];
        if (ext.url?.includes('soaFootnotes') && ext.valueString) {
          try {
            const soaFns = JSON.parse(ext.valueString as string) as string[];
            if (soaFns.length > 0) {
              return { footnotes: soaFns, footnoteExtIndex: i };
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
    // Fall back to provenance footnotes
    return { footnotes: provenance?.footnotes || [], footnoteExtIndex: -1 };
  }, [studyDesign, provenance]);

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

      {/* Error display */}
      {lastError && (
        <div className="flex items-center gap-2 text-red-600 text-sm p-2 bg-red-50 rounded-md">
          <AlertCircle className="h-4 w-4" />
          {lastError}
        </div>
      )}

      {/* Grid - always editable, changes go to semantic draft */}
      <Card>
        <CardContent className="p-0">
          <div className="h-[600px]">
            <SoAGrid
              key={revision || 'initial'}
              model={filteredModel}
              onCellClick={handleCellClick}
              editable={true}
              availableFootnotes={footnotes.map((_, i) => String.fromCharCode(97 + i))}
            />
          </div>
        </CardContent>
      </Card>

      {/* Footnotes */}
      {footnotes.length > 0 && (
        <FootnotePanel
          footnotes={footnotes}
          selectedFootnoteRefs={selectedFootnoteRefs}
          editBasePath={footnoteExtIndex >= 0 ? `/study/versions/0/studyDesigns/0/extensionAttributes/${footnoteExtIndex}/soaFootnotes` : undefined}
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

      {/* Enrichment Instances (from execution model) */}
      {tableModel.enrichmentInstances.length > 0 && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <span>Enrichment Instances</span>
              <span className="text-xs font-normal text-muted-foreground">
                ({tableModel.enrichmentInstances.length} schedule instances inferred from execution model, not in PDF SoA)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="py-3">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 pr-4 font-medium">Instance</th>
                    <th className="pb-2 pr-4 font-medium">Activity</th>
                    <th className="pb-2 pr-4 font-medium">Visit</th>
                    <th className="pb-2 pr-4 font-medium">Day</th>
                    <th className="pb-2 font-medium">Epoch</th>
                  </tr>
                </thead>
                <tbody>
                  {tableModel.enrichmentInstances.slice(0, 20).map((inst) => (
                    <tr key={inst.id} className="border-b border-muted/50 hover:bg-muted/20">
                      <td className="py-1.5 pr-4">{inst.name}</td>
                      <td className="py-1.5 pr-4 text-muted-foreground">{inst.activityName || '-'}</td>
                      <td className="py-1.5 pr-4 text-muted-foreground">{inst.encounterName || '-'}</td>
                      <td className="py-1.5 pr-4 text-muted-foreground">{inst.scheduledDay ?? '-'}</td>
                      <td className="py-1.5 text-muted-foreground">{inst.epochName || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {tableModel.enrichmentInstances.length > 20 && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Showing 20 of {tableModel.enrichmentInstances.length} enrichment instances
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Protocol Activities not in SoA (from procedure enrichment) */}
      {tableModel.procedureActivities.length > 0 && (
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <span>Protocol Activities (Not in SoA)</span>
              <span className="text-xs font-normal text-muted-foreground">
                ({tableModel.procedureActivities.length} activities extracted from protocol but not scheduled in SoA table)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="py-3">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 text-sm">
              {tableModel.procedureActivities.map((activity) => (
                <div
                  key={activity.id}
                  className="px-2 py-1 bg-muted rounded text-muted-foreground"
                  title={activity.description || activity.name}
                >
                  {activity.label || activity.name}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default SoAView;
