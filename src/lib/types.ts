export type NodeGroup = 'Person' | 'Event' | 'Concept' | 'Object' | 'Group' | 'Work'

export interface GraphNode {
  id: string
  label_en: string
  label_ko: string
  group: NodeGroup | string
  description: string
  evidenceType: string
  pageReferences: string
  chapters: string[]
  wikibaseUrl: string | null
}

export interface GraphEdge {
  source: string
  target: string
  predicate: string
  pageRef: string
  note: string
  status: string
}

export interface GraphData {
  generatedAt: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export type Lang = 'en' | 'ko'
