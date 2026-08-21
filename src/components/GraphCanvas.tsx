import { useEffect, useMemo, useRef } from 'react'
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape'
import coseBilkent from 'cytoscape-cose-bilkent'
import CytoscapeComponent from 'react-cytoscapejs'
import type { GraphData, GraphEdge, GraphNode, Lang } from '../lib/types'
import { cytoscapeStylesheet } from '../lib/graphStyles'

cytoscape.use(coseBilkent)

interface Props {
  graph: GraphData
  lang: Lang
  activeTypes: Set<string>
  activeChapter: string | null
  highlightedId: string | null
  onSelectNode: (node: GraphNode) => void
  onSelectEdge: (edge: GraphEdge) => void
  onCyReady: (cy: Core) => void
}

function nodeMatchesFilters(node: GraphNode, activeTypes: Set<string>, activeChapter: string | null) {
  const typeOk = activeTypes.size === 0 || activeTypes.has(node.group)
  const chapterOk = !activeChapter || node.chapters.includes(activeChapter) || node.chapters.includes('ALL')
  return typeOk && chapterOk
}

export default function GraphCanvas({
  graph,
  lang,
  activeTypes,
  activeChapter,
  highlightedId,
  onSelectNode,
  onSelectEdge,
  onCyReady,
}: Props) {
  const cyRef = useRef<Core | null>(null)

  const nodeById = useMemo(() => {
    const m = new Map<string, GraphNode>()
    graph.nodes.forEach((n) => m.set(n.id, n))
    return m
  }, [graph])

  const degreeById = useMemo(() => {
    const m = new Map<string, number>()
    graph.edges.forEach((e) => {
      m.set(e.source, (m.get(e.source) ?? 0) + 1)
      m.set(e.target, (m.get(e.target) ?? 0) + 1)
    })
    return m
  }, [graph])

  const elements: ElementDefinition[] = useMemo(() => {
    const nodeEls: ElementDefinition[] = graph.nodes.map((n) => ({
      data: {
        id: n.id,
        group: n.group,
        label: lang === 'en' ? n.label_en : n.label_ko || n.label_en,
        degree: degreeById.get(n.id) ?? 0,
      },
    }))
    const edgeEls: ElementDefinition[] = graph.edges.map((e, i) => {
      const srcEvidence = nodeById.get(e.source)?.evidenceType
      const tgtEvidence = nodeById.get(e.target)?.evidenceType
      const isModeling = srcEvidence === 'Modeling' || tgtEvidence === 'Modeling'
      const data: Record<string, unknown> = {
        id: `edge-${i}`,
        source: e.source,
        target: e.target,
        predicate: e.predicate,
      }
      if (isModeling) data.isModeling = true
      return { data }
    })
    return [...nodeEls, ...edgeEls]
  }, [graph, lang, degreeById, nodeById])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().forEach((n) => {
      const node = nodeById.get(n.id())
      const match = node ? nodeMatchesFilters(node, activeTypes, activeChapter) : true
      n.toggleClass('dimmed', !match)
    })
    cy.edges().forEach((e) => {
      const src = nodeById.get(e.source().id())
      const tgt = nodeById.get(e.target().id())
      const match =
        (src ? nodeMatchesFilters(src, activeTypes, activeChapter) : true) &&
        (tgt ? nodeMatchesFilters(tgt, activeTypes, activeChapter) : true)
      e.toggleClass('dimmed', !match)
    })
  }, [activeTypes, activeChapter, nodeById, elements])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().removeClass('highlighted')
    if (highlightedId) {
      const n = cy.getElementById(highlightedId)
      if (n.nonempty()) {
        n.addClass('highlighted')
        cy.animate({ center: { eles: n }, zoom: 1.5 }, { duration: 400 })
      }
    }
  }, [highlightedId])

  return (
    <CytoscapeComponent
      elements={elements}
      stylesheet={cytoscapeStylesheet}
      style={{ width: '100%', height: '100%' }}
      layout={{ name: 'cose-bilkent', animate: false } as never}
      cy={(cy) => {
        if (cyRef.current === cy) return
        cyRef.current = cy
        onCyReady(cy)
        cy.on('tap', 'node', (evt) => {
          const node = nodeById.get(evt.target.id())
          if (node) onSelectNode(node)
        })
        cy.on('tap', 'edge', (evt) => {
          const idx = Number(String(evt.target.id()).replace('edge-', ''))
          const edge = graph.edges[idx]
          if (edge) onSelectEdge(edge)
        })
      }}
    />
  )
}
