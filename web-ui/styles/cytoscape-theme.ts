// Cytoscape stylesheet definitions
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const cytoscapeStyles: any[] = [
  // Base node style
  {
    selector: 'node',
    style: {
      'label': 'data(label)',
      'text-wrap': 'wrap',
      'text-max-width': '80px',
      'font-size': '11px',
      'text-valign': 'bottom',
      'text-margin-y': 5,
      'color': '#374151',
    },
  },
  
  // Epoch nodes (background grouping) - left justified
  {
    selector: 'node[type="epoch"]',
    style: {
      'background-color': '#dbeafe',
      'border-width': 2,
      'border-color': '#3b82f6',
      'shape': 'round-rectangle',
      'width': 120,
      'height': 40,
      'font-size': '12px',
      'font-weight': 'bold',
      'text-valign': 'center',
      'text-halign': 'center',
    },
  },
  
  // Timing/encounter nodes (circles)
  {
    selector: 'node[type="timing"]',
    style: {
      'background-color': '#ffffff',
      'border-width': 2,
      'border-color': '#374151',
      'shape': 'ellipse',
      'width': 50,
      'height': 50,
      'text-valign': 'bottom',
      'text-margin-y': 5,
    },
  },
  
  // Timing nodes that are anchors - label above, anchor icon as background
  {
    selector: 'node[type="timing"][?isAnchor]',
    style: {
      'background-color': '#fef3c7',
      'border-width': 3,
      'border-color': '#d97706',
      'width': 55,
      'height': 55,
      'text-valign': 'top',
      'text-margin-y': -8,
      'label': 'data(label)',
      'font-size': '11px',
      'background-image': 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNiNDUzMDkiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjUiIHI9IjMiLz48bGluZSB4MT0iMTIiIHkxPSIyMiIgeDI9IjEyIiB5Mj0iOCIvPjxwYXRoIGQ9Ik01IDEySDJhMTAgMTAgMCAwIDAgMjAgMGgtMyIvPjwvc3ZnPg==',
      'background-width': '50%',
      'background-height': '50%',
      'background-position-x': '50%',
      'background-position-y': '50%',
    },
  },
  
  // Anchor-timing class - same styling
  {
    selector: 'node.anchor-timing',
    style: {
      'background-color': '#fef3c7',
      'border-width': 3,
      'border-color': '#d97706',
      'text-valign': 'top',
      'text-margin-y': -8,
      'background-image': 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNiNDUzMDkiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjUiIHI9IjMiLz48bGluZSB4MT0iMTIiIHkxPSIyMiIgeDI9IjEyIiB5Mj0iOCIvPjxwYXRoIGQ9Ik01IDEySDJhMTAgMTAgMCAwIDAgMjAgMGgtMyIvPjwvc3ZnPg==',
      'background-width': '50%',
      'background-height': '50%',
    },
  },
  
  // Activity nodes (white with green border)
  {
    selector: 'node[type="activity"]',
    style: {
      'background-color': '#ffffff',
      'border-width': 2,
      'border-color': '#22c55e',
      'shape': 'round-rectangle',
      'width': 140,
      'height': 45,
      'text-wrap': 'wrap',
      'text-max-width': '130px',
      'font-size': '10px',
      'text-valign': 'center',
      'text-halign': 'center',
    },
  },
  
  // Instance nodes (grey circle)
  {
    selector: 'node[type="instance"]',
    style: {
      'background-color': '#9ca3af',
      'border-width': 0,
      'shape': 'ellipse',
      'width': 40,
      'height': 40,
      'color': '#ffffff',
      'text-valign': 'center',
      'text-halign': 'center',
    },
  },
  
  // Condition nodes (dashed orange rounded rectangle)
  {
    selector: 'node[type="condition"]',
    style: {
      'background-color': '#fff7ed',
      'border-width': 2,
      'border-color': '#f97316',
      'border-style': 'dashed',
      'shape': 'round-rectangle',
      'width': 120,
      'height': 50,
      'font-size': '10px',
      'text-valign': 'center',
      'text-halign': 'center',
    },
  },
  
  // Halo (dashed ellipse behind target timing node)
  {
    selector: 'node[type="halo"]',
    style: {
      'background-color': 'transparent',
      'border-width': 1,
      'border-color': '#94a3b8',
      'border-style': 'dashed',
      'shape': 'ellipse',
      'width': 70,
      'height': 70,
      'z-index': -1,
    },
  },
  
  // Anchor nodes (Fixed Reference - label above, icon centered)
  {
    selector: 'node[type="anchor"]',
    style: {
      'background-color': '#fef3c7',
      'border-width': 3,
      'border-color': '#d97706',
      'shape': 'ellipse',
      'width': 55,
      'height': 55,
      'text-valign': 'top',
      'text-margin-y': -8,
      'label': 'data(label)',
      'font-size': '11px',
      'background-image': 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNiNDUzMDkiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjUiIHI9IjMiLz48bGluZSB4MT0iMTIiIHkxPSIyMiIgeDI9IjEyIiB5Mj0iOCIvPjxwYXRoIGQ9Ik01IDEySDJhMTAgMTAgMCAwIDAgMjAgMGgtMyIvPjwvc3ZnPg==',
      'background-width': '50%',
      'background-height': '50%',
    },
  },
  
  // Timing detail nodes (non-anchor timing relationships)
  {
    selector: 'node.timing-detail-node',
    style: {
      'background-color': '#ffffff',
      'border-width': 2,
      'border-color': '#003366',
      'shape': 'ellipse',
      'width': 65,
      'height': 65,
      'text-valign': 'center',
      'text-halign': 'center',
      'text-wrap': 'wrap',
      'text-max-width': '55px',
      'font-size': '9px',
      'color': '#003366',
    },
  },
  
  // Locked nodes indicator
  {
    selector: 'node.locked',
    style: {
      'border-width': 3,
      'border-color': '#3b82f6',
    },
  },
  
  // Highlighted nodes
  {
    selector: 'node.highlighted',
    style: {
      'background-color': '#fef08a',
      'border-color': '#eab308',
    },
  },
  
  // Selected nodes
  {
    selector: 'node:selected',
    style: {
      'border-width': 3,
      'border-color': '#6366f1',
      'background-color': '#eef2ff',
    },
  },
  
  // Base edge style
  {
    selector: 'edge',
    style: {
      'width': 2,
      'line-color': '#9ca3af',
      'target-arrow-color': '#9ca3af',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'arrow-scale': 0.8,
    },
  },
  
  // Sequence edges (between encounters)
  {
    selector: 'edge[type="sequence"]',
    style: {
      'line-color': '#6b7280',
      'target-arrow-color': '#6b7280',
      'line-style': 'solid',
    },
  },
  
  // Timing edges
  {
    selector: 'edge[type="timing"]',
    style: {
      'line-color': '#003366',
      'target-arrow-color': '#003366',
      'curve-style': 'bezier',
      'width': 2,
    },
  },
  
  // Timing edges with labels
  {
    selector: 'edge.timing-edge',
    style: {
      'line-color': '#003366',
      'target-arrow-color': '#003366',
      'label': 'data(label)',
      'font-size': '9px',
      'color': '#003366',
      'font-weight': 'bold',
      'text-rotation': 'autorotate',
      'text-margin-y': -8,
    },
  },
  
  // Activity edges (from encounter to activity)
  {
    selector: 'edge[type="activity"]',
    style: {
      'line-color': '#22c55e',
      'target-arrow-color': '#22c55e',
      'line-style': 'dashed',
      'width': 1.5,
    },
  },
  
  // Condition edges
  {
    selector: 'edge[type="condition"]',
    style: {
      'line-style': 'dashed',
      'line-color': '#f97316',
      'target-arrow-color': '#f97316',
    },
  },
  
  // Selected edges
  {
    selector: 'edge:selected',
    style: {
      'width': 3,
      'line-color': '#6366f1',
      'target-arrow-color': '#6366f1',
    },
  },
  
  // Epoch transition edges (arrows between epochs)
  {
    selector: 'edge[type="transition"]',
    style: {
      'line-color': '#94a3b8',
      'target-arrow-color': '#94a3b8',
      'target-arrow-shape': 'triangle',
      'curve-style': 'straight',
      'width': 3,
      'arrow-scale': 1.2,
    },
  },
  
  // Epoch transition with class
  {
    selector: 'edge.epoch-transition',
    style: {
      'line-color': '#64748b',
      'target-arrow-color': '#64748b',
      'line-style': 'solid',
      'width': 2,
    },
  },
  
  // Execution model anchor nodes
  {
    selector: 'node.execution-anchor',
    style: {
      'background-color': '#fef3c7',
      'border-width': 3,
      'border-color': '#d97706',
      'shape': 'diamond',
      'width': 70,
      'height': 70,
      'text-valign': 'bottom',
      'text-margin-y': 8,
      'font-size': '10px',
      'font-weight': 'bold',
      'color': '#92400e',
    },
  },
  
  // Visit window indicator nodes
  {
    selector: 'node[type="window"]',
    style: {
      'background-color': '#ecfdf5',
      'border-width': 2,
      'border-color': '#10b981',
      'border-style': 'dashed',
      'shape': 'round-rectangle',
      'width': 90,
      'height': 24,
      'font-size': '9px',
      'text-valign': 'center',
      'text-halign': 'center',
      'color': '#059669',
    },
  },
  
  // Encounters with visit windows
  {
    selector: 'node.has-window',
    style: {
      'border-width': 3,
      'border-color': '#10b981',
    },
  },
  
  // Swimlane background nodes
  {
    selector: 'node[type="swimlane"]',
    style: {
      'background-color': '#f8fafc',
      'background-opacity': 0.5,
      'border-width': 1,
      'border-color': '#e2e8f0',
      'border-style': 'dashed',
      'shape': 'round-rectangle',
      'z-index': -10,
    },
  },
  
  // Window edges
  {
    selector: 'edge[type="window"]',
    style: {
      'line-color': '#86efac',
      'line-style': 'dashed',
      'width': 1,
      'target-arrow-shape': 'none',
    },
  },
  
  // Anchor-to-encounter edges
  {
    selector: 'edge.anchor-edge',
    style: {
      'line-color': '#d97706',
      'line-style': 'dashed',
      'width': 1.5,
      'target-arrow-shape': 'diamond',
      'target-arrow-color': '#d97706',
      'arrow-scale': 0.6,
      'curve-style': 'straight',
    },
  },
  
  // UNS Decision nodes (diamond shape, amber)
  {
    selector: 'node[type="decision"]',
    style: {
      'background-color': '#fffbeb',
      'border-width': 2,
      'border-color': '#d97706',
      'border-style': 'dashed',
      'shape': 'diamond',
      'width': 60,
      'height': 60,
      'font-size': '9px',
      'text-valign': 'bottom',
      'text-margin-y': 8,
      'text-wrap': 'wrap',
      'text-max-width': '90px',
      'color': '#92400e',
      'font-weight': 'bold',
    },
  },
  
  // Decision branch edges (dashed amber — event triggers UNS visit)
  {
    selector: 'edge[type="decision-branch"]',
    style: {
      'line-color': '#f59e0b',
      'target-arrow-color': '#f59e0b',
      'line-style': 'dashed',
      'width': 2,
      'curve-style': 'unbundled-bezier',
      'label': 'data(label)',
      'font-size': '8px',
      'color': '#b45309',
      'text-rotation': 'autorotate',
      'text-margin-y': -8,
    },
  },
  
  // Decision default edges (solid grey — continue on main timeline)
  {
    selector: 'edge[type="decision-default"]',
    style: {
      'line-color': '#9ca3af',
      'target-arrow-color': '#9ca3af',
      'line-style': 'solid',
      'width': 2,
      'curve-style': 'bezier',
      'label': 'data(label)',
      'font-size': '8px',
      'color': '#6b7280',
      'text-rotation': 'autorotate',
      'text-margin-y': -8,
    },
  },
];

export default cytoscapeStyles;
