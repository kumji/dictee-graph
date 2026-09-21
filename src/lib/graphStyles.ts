import type { StylesheetJsonBlock } from 'cytoscape'

export const GROUP_COLORS: Record<string, string> = {
  Person: '#3B82F6',
  Event: '#EF4444',
  Concept: '#8B5CF6',
  Object: '#F59E0B',
  Group: '#10B981',
  Work: '#EC4899',
}

const DEFAULT_COLOR = '#6B7280'

export const cytoscapeStylesheet: StylesheetJsonBlock[] = [
  {
    selector: 'node',
    style: {
      'background-color': (ele: cytoscape.NodeSingular) => GROUP_COLORS[ele.data('group')] ?? DEFAULT_COLOR,
      label: 'data(label)',
      color: '#111827',
      'font-size': 10,
      'text-valign': 'bottom',
      'text-margin-y': 4,
      width: (ele: cytoscape.NodeSingular) => 18 + Math.min(ele.data('degree') ?? 0, 12) * 4,
      height: (ele: cytoscape.NodeSingular) => 18 + Math.min(ele.data('degree') ?? 0, 12) * 4,
      'border-width': 1.5,
      'border-color': '#ffffff',
      'text-outline-width': 2,
      'text-outline-color': '#f9fafb',
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 3,
      'border-color': '#111827',
    },
  },
  {
    selector: 'node.dimmed',
    style: {
      opacity: 0.15,
    },
  },
  {
    selector: 'node.highlighted',
    style: {
      'border-width': 4,
      'border-color': '#111827',
    },
  },
  {
    selector: 'edge',
    style: {
      width: 1.5,
      'line-color': '#9CA3AF',
      'target-arrow-color': '#9CA3AF',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      label: 'data(predicate)',
      'font-size': 8,
      color: '#4B5563',
      'text-background-color': '#f9fafb',
      'text-background-opacity': 0.8,
      'text-background-padding': '1px',
      'text-rotation': 'autorotate',
    },
  },
  {
    selector: 'edge[isModeling]',
    style: {
      'line-style': 'dashed',
      'line-dash-pattern': [6, 3],
    },
  },
  {
    selector: 'edge[schemaViolation]',
    style: {
      'line-color': '#D1D5DB',
      'target-arrow-color': '#D1D5DB',
      width: 2,
    },
  },
  {
    selector: 'edge.dimmed',
    style: {
      opacity: 0.15,
    },
  },
]
