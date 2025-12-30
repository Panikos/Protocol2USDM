import type { Stylesheet } from 'cytoscape';

export const cytoscapeStyles: Stylesheet[] = [
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
  
  // Epoch nodes (background grouping)
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
  
  // Timing/encounter nodes (white circle)
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
      'text-margin-y': 8,
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
      'width': 100,
      'height': 36,
      'text-wrap': 'wrap',
      'text-max-width': '90px',
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
      'line-color': '#3b82f6',
      'target-arrow-color': '#3b82f6',
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
];

export default cytoscapeStyles;
