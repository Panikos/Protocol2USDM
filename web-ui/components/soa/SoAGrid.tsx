'use client';

import { useCallback, useMemo, useRef } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { 
  ColDef, 
  ColGroupDef,
  GridReadyEvent,
  RowDragEndEvent,
  ColumnMovedEvent,
  GridApi,
} from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
// Note: ag-grid-enterprise removed - requires license key

import { ProvenanceCellRenderer } from './ProvenanceCellRenderer';
import type { SoATableModel, SoACell } from '@/lib/adapters/toSoATableModel';
import { useOverlayStore } from '@/stores/overlayStore';

interface SoAGridProps {
  model: SoATableModel;
  onCellClick?: (activityId: string, visitId: string, cell: SoACell | undefined) => void;
}

export function SoAGrid({ model, onCellClick }: SoAGridProps) {
  const gridRef = useRef<AgGridReact>(null);
  const gridApiRef = useRef<GridApi | null>(null);
  
  const { updateDraftTableOrder } = useOverlayStore();

  // Build row data from model
  const rowData = useMemo(() => {
    return model.rows.map((row) => {
      const rowObj: Record<string, unknown> = {
        id: row.id,
        activityName: row.name,
        groupName: row.groupName || '',
        _rowData: row,
      };

      // Add cell values for each column
      for (const col of model.columns) {
        const cell = model.cells.get(`${row.id}|${col.id}`);
        rowObj[`col_${col.id}`] = cell?.mark || '';
      }

      return rowObj;
    });
  }, [model]);

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

    // Activity name column
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
          },
          headerClass: 'text-center ag-header-cell-wrap',
          cellClass: 'text-center p-0',
          wrapHeaderText: true,
          autoHeaderHeight: true,
        });
      }
    }

    return defs;
  }, [model]);

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
    if (!field?.startsWith('col_') || !onCellClick) return;

    const visitId = field.replace('col_', '');
    const activityId = event.data.id;
    const cell = model.cells.get(`${activityId}|${visitId}`);
    
    onCellClick(activityId, visitId, cell);
  }, [model.cells, onCellClick]);

  return (
    <div className="ag-theme-alpine w-full h-full">
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
        rowHeight={36}
        headerHeight={40}
        groupHeaderHeight={44}
        suppressRowClickSelection={true}
        enableCellTextSelection={true}
      />
    </div>
  );
}

export default SoAGrid;
