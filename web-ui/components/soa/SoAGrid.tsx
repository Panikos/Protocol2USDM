'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { 
  ColDef, 
  ColGroupDef,
  GridReadyEvent,
  RowDragEndEvent,
  ColumnMovedEvent,
  GridApi,
  CellDoubleClickedEvent,
} from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

import { ProvenanceCellRenderer } from './ProvenanceCellRenderer';
import { SoACellEditor } from './SoACellEditor';
import type { SoATableModel, SoACell } from '@/lib/adapters/toSoATableModel';
import { useOverlayStore } from '@/stores/overlayStore';
import { useSoAEditStore } from '@/stores/soaEditStore';
import { useEditModeStore } from '@/stores/editModeStore';
import type { CellMark } from '@/lib/soa/processor';

interface SoAGridProps {
  model: SoATableModel;
  onCellClick?: (activityId: string, visitId: string, cell: SoACell | undefined) => void;
  editable?: boolean;
  availableFootnotes?: string[];
}

export function SoAGrid({ model, onCellClick, editable = false, availableFootnotes = [] }: SoAGridProps) {
  const gridRef = useRef<AgGridReact>(null);
  const gridApiRef = useRef<GridApi | null>(null);
  
  const { updateDraftTableOrder } = useOverlayStore();
  const { setCellMark, isUserEdited, getPendingMark, setActivityName, setEncounterName, committedCellEdits } = useSoAEditStore();
  const isEditMode = useEditModeStore((s) => s.isEditMode);
  const canEdit = editable && isEditMode;
  
  // Use ref for committedCellEdits to avoid recreating columnDefs (which breaks ag-grid column groups)
  const committedEditsRef = useRef(committedCellEdits);
  committedEditsRef.current = committedCellEdits;
  
  // Refresh cells when edits change
  useEffect(() => {
    if (gridApiRef.current) {
      // Force redraw all rows to pick up edit changes
      gridApiRef.current.redrawRows();
    }
  }, [committedCellEdits]);
  
  // State for editing activity/encounter names
  const [editingActivityId, setEditingActivityId] = useState<string | null>(null);
  const [editingActivityName, setEditingActivityName] = useState('');
  const [editingEncounterId, setEditingEncounterId] = useState<string | null>(null);
  const [editingEncounterName, setEditingEncounterName] = useState('');
  
  // State for cell editor popup
  const [editingCell, setEditingCell] = useState<{
    activityId: string;
    encounterId: string;
    currentMark: CellMark;
    footnoteRefs: string[];
    rect: DOMRect;
  } | null>(null);

  // Handle cell edit save
  const handleCellSave = useCallback((mark: CellMark, footnoteRefs: string[]) => {
    if (editingCell) {
      setCellMark(editingCell.activityId, editingCell.encounterId, mark, footnoteRefs);
      setEditingCell(null);
      gridApiRef.current?.refreshCells();
    }
  }, [editingCell, setCellMark]);

  // Handle keyboard shortcuts for quick cell editing
  const onCellKeyDown = useCallback((event: any) => {
    if (!canEdit) return;
    const field = event.colDef?.field;
    if (!field?.startsWith('col_')) return;

    const keyEvent = event.event as KeyboardEvent;
    const key = keyEvent.key.toUpperCase();
    const encounterId = field.replace('col_', '');
    const activityId = event.data?.id;
    if (!activityId) return;

    // Quick-mark shortcuts
    const quickMarks: Record<string, CellMark> = {
      'X': 'X',
      'O': 'O',
      '-': '\u2212',  // minus sign
    };

    if (quickMarks[key]) {
      keyEvent.preventDefault();
      const cell = model.cells.get(`${activityId}|${encounterId}`);
      setCellMark(activityId, encounterId, quickMarks[key], cell?.footnoteRefs ?? []);
      return;
    }

    // Delete/Backspace to clear
    if (keyEvent.key === 'Delete' || keyEvent.key === 'Backspace') {
      keyEvent.preventDefault();
      setCellMark(activityId, encounterId, 'clear', []);
      return;
    }

    // Enter to open full editor popup
    if (keyEvent.key === 'Enter') {
      keyEvent.preventDefault();
      const cell = model.cells.get(`${activityId}|${encounterId}`);
      const pendingEdit = getPendingMark(activityId, encounterId);
      const cellElement = event.event?.target as HTMLElement;
      const rect = cellElement?.getBoundingClientRect();
      if (rect) {
        setEditingCell({
          activityId,
          encounterId,
          currentMark: pendingEdit?.mark ?? (cell?.mark as CellMark) ?? null,
          footnoteRefs: pendingEdit?.footnoteRefs ?? cell?.footnoteRefs ?? [],
          rect,
        });
      }
      return;
    }
  }, [canEdit, model.cells, setCellMark, getPendingMark]);

  // Handle double-click to edit
  const onCellDoubleClicked = useCallback((event: CellDoubleClickedEvent) => {
    if (!canEdit) return;
    const field = event.colDef.field;
    if (!field?.startsWith('col_')) return;

    const encounterId = field.replace('col_', '');
    const activityId = event.data.id;
    const cell = model.cells.get(`${activityId}|${encounterId}`);
    const pendingEdit = getPendingMark(activityId, encounterId);
    
    // Get cell element position for popup
    const cellElement = event.event?.target as HTMLElement;
    const rect = cellElement?.getBoundingClientRect();
    
    if (rect) {
      setEditingCell({
        activityId,
        encounterId,
        currentMark: pendingEdit?.mark ?? (cell?.mark as CellMark) ?? null,
        footnoteRefs: pendingEdit?.footnoteRefs ?? cell?.footnoteRefs ?? [],
        rect,
      });
    }
  }, [canEdit, model.cells, getPendingMark]);

  // Build row data from model, incorporating committed edits
  const rowData = useMemo(() => {
    return model.rows.map((row) => {
      const rowObj: Record<string, unknown> = {
        id: row.id,
        activityName: row.name,
        groupName: row.groupName || '',
        _rowData: row,
      };

      // Add cell values for each column, checking committed edits first
      for (const col of model.columns) {
        const cellKey = `${row.id}|${col.id}`;
        const edit = committedCellEdits.get(cellKey);
        if (edit) {
          // Use edit value (clear means empty)
          rowObj[`col_${col.id}`] = edit.mark === 'clear' ? '' : edit.mark;
        } else {
          const cell = model.cells.get(cellKey);
          rowObj[`col_${col.id}`] = cell?.mark || '';
        }
      }

      return rowObj;
    });
  }, [model, committedCellEdits]);

  // Build column definitions
  const columnDefs = useMemo((): (ColDef | ColGroupDef)[] => {
    const defs: (ColDef | ColGroupDef)[] = [];

    // Category column (shown as regular column without enterprise license)
    if (model.rowGroups.length > 0) {
      defs.push({
        headerName: 'Category',
        field: 'groupName',
        pinned: 'left',
        width: 160,
        suppressMovable: true,
        cellStyle: {
          fontWeight: '600',
          backgroundColor: '#f3f4f6',
        },
      });
    }

    // Activity name column - editable when in edit mode
    defs.push({
      headerName: 'Activity',
      field: 'activityName',
      pinned: 'left',
      width: 220,
      suppressMovable: true,
      cellStyle: { 
        fontWeight: '500',
        backgroundColor: '#fafafa',
      },
      rowDrag: true,
      editable: canEdit,
      cellClass: canEdit ? 'cursor-pointer hover:bg-blue-50' : '',
      onCellValueChanged: (params) => {
        if (params.newValue !== params.oldValue) {
          setActivityName(params.data.id, params.newValue);
        }
      },
    });

    // Group columns by epoch
    for (const group of model.columnGroups) {
      const children: ColDef[] = model.columns
        .filter((col) => col.epochId === group.id)
        .map((col) => ({
          headerName: col.timing || col.name,
          field: `col_${col.id}`,
          minWidth: 80,
          flex: 1,
          cellRenderer: ProvenanceCellRenderer,
          cellRendererParams: {
            columnId: col.id,
            cellMap: model.cells,
            pendingEditsRef: committedEditsRef,
          },
          headerClass: 'text-center ag-header-cell-wrap',
          cellClass: 'text-center p-0',
          suppressMenu: true,
          wrapHeaderText: true,
          autoHeaderHeight: true,
        }));

      defs.push({
        headerName: group.name,
        headerClass: 'bg-blue-50 font-semibold ag-header-cell-wrap',
        children,
        wrapHeaderText: true,
        autoHeaderHeight: true,
      } as ColGroupDef);
    }

    // If no groups, add columns directly
    if (model.columnGroups.length === 0) {
      for (const col of model.columns) {
        defs.push({
          headerName: col.timing || col.name,
          field: `col_${col.id}`,
          minWidth: 80,
          flex: 1,
          cellRenderer: ProvenanceCellRenderer,
          cellRendererParams: {
            columnId: col.id,
            cellMap: model.cells,
            pendingEditsRef: committedEditsRef,
          },
          headerClass: 'text-center ag-header-cell-wrap',
          cellClass: 'text-center p-0',
          wrapHeaderText: true,
          autoHeaderHeight: true,
        });
      }
    }

    return defs;
  }, [model, canEdit, setActivityName]);

  // Default column settings
  const defaultColDef = useMemo<ColDef>(() => ({
    sortable: false,
    filter: false,
    resizable: true,
    suppressMovable: false,
  }), []);

  
  // Grid ready handler
  const onGridReady = useCallback((params: GridReadyEvent) => {
    gridApiRef.current = params.api;
  }, []);

  // Row drag handler - update overlay
  const onRowDragEnd = useCallback((event: RowDragEndEvent) => {
    const api = event.api;
    const newRowOrder: string[] = [];
    
    api.forEachNode((node) => {
      if (node.data?.id) {
        newRowOrder.push(node.data.id);
      }
    });

    updateDraftTableOrder(newRowOrder, undefined);
  }, [updateDraftTableOrder]);

  // Column moved handler - update overlay
  const onColumnMoved = useCallback((event: ColumnMovedEvent) => {
    if (!event.finished || !gridApiRef.current) return;

    const allColumns = gridApiRef.current.getAllDisplayedColumns();
    const newColumnOrder: string[] = [];

    for (const col of allColumns) {
      const field = col.getColDef().field;
      if (field?.startsWith('col_')) {
        newColumnOrder.push(field.replace('col_', ''));
      }
    }

    if (newColumnOrder.length > 0) {
      updateDraftTableOrder(undefined, newColumnOrder);
    }
  }, [updateDraftTableOrder]);

  // Cell click handler
  const onCellClicked = useCallback((event: any) => {
    const field = event.colDef.field;
    if (!field?.startsWith('col_')) return;

    const visitId = field.replace('col_', '');
    const activityId = event.data.id;
    const cell = model.cells.get(`${activityId}|${visitId}`);
    
    if (onCellClick) {
      onCellClick(activityId, visitId, cell);
    }
  }, [model.cells, onCellClick]);

  return (
    <div className="ag-theme-alpine w-full h-full relative">
      <AgGridReact
        ref={gridRef}
        rowData={rowData}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        getRowId={(params) => params.data.id}
        animateRows={true}
        rowDragManaged={true}
        suppressMoveWhenRowDragging={true}
        onGridReady={onGridReady}
        onRowDragEnd={onRowDragEnd}
        onColumnMoved={onColumnMoved}
        onCellClicked={onCellClicked}
        onCellDoubleClicked={onCellDoubleClicked}
        onCellKeyDown={onCellKeyDown}
        rowHeight={36}
        suppressCellFocus={false}
        headerHeight={40}
        groupHeaderHeight={44}
        suppressRowClickSelection={true}
      />
      
      {/* Cell Editor Popup */}
      {editingCell && (
        <div
          className="fixed z-50"
          style={{
            top: editingCell.rect.bottom + 4,
            left: editingCell.rect.left,
          }}
        >
          <SoACellEditor
            activityId={editingCell.activityId}
            encounterId={editingCell.encounterId}
            currentMark={editingCell.currentMark}
            footnoteRefs={editingCell.footnoteRefs}
            availableFootnotes={availableFootnotes}
            onSave={handleCellSave}
            stopEditing={() => setEditingCell(null)}
          />
        </div>
      )}
      
      {/* Backdrop to close editor */}
      {editingCell && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setEditingCell(null)}
        />
      )}
    </div>
  );
}

export default SoAGrid;
