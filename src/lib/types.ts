export type NodeGroup = 'Person' | 'Event' | 'Concept' | 'Object' | 'Group' | 'Work'

export interface GraphNode {
  id: string
  label_en: string
  label_ko: string
  group: NodeGroup | string
  description: string
  evidenceType: string
  equivalentUri: string | null
  broader: string[]
  closeMatch: string[]
  documentedIn: string[]
}

export interface GraphEdge {
  source: string
  target: string
  predicate: string
  documentedIn: string[]
  schemaViolation: boolean
}

export interface GraphData {
  generatedAt: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export type Lang = 'en' | 'ko'
