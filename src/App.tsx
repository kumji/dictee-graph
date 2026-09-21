import { useEffect, useMemo, useState } from 'react'
import type { GraphData, GraphEdge, GraphNode, Lang } from './lib/types'
import GraphCanvas from './components/GraphCanvas'
import DetailPanel from './components/DetailPanel'
import FilterBar from './components/FilterBar'
import SearchBox from './components/SearchBox'

type Selection = { type: 'node'; data: GraphNode } | { type: 'edge'; data: GraphEdge } | null

export default function App() {
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lang, setLang] = useState<Lang>('en')
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set())
  const [selection, setSelection] = useState<Selection>(null)
  const [highlightedId, setHighlightedId] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/graph.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`graph.json 로드 실패: ${res.status}`)
        return res.json()
      })
      .then((data: GraphData) => setGraph(data))
      .catch((err) => setError(String(err)))
  }, [])

  const types = useMemo(() => {
    if (!graph) return []
    return Array.from(new Set(graph.nodes.map((n) => n.group))).sort()
  }, [graph])

  const toggleType = (type: string) => {
    setActiveTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  if (error) {
    return <div className="p-6 text-sm text-red-600">그래프 데이터를 불러오지 못했습니다: {error}</div>
  }

  if (!graph) {
    return <div className="p-6 text-sm text-gray-500">그래프 로딩 중…</div>
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-4 border-b border-gray-200 bg-white px-4 py-2">
        <h1 className="text-base font-semibold text-gray-900">Dictée LOD Graph</h1>
        <SearchBox
          nodes={graph.nodes}
          lang={lang}
          onSelect={(n) => {
            setSelection({ type: 'node', data: n })
            setHighlightedId(n.id)
          }}
        />
      </header>
      <FilterBar
        types={types}
        activeTypes={activeTypes}
        onToggleType={toggleType}
        lang={lang}
        onToggleLang={() => setLang((l) => (l === 'en' ? 'ko' : 'en'))}
      />
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1">
          <GraphCanvas
            graph={graph}
            lang={lang}
            activeTypes={activeTypes}
            highlightedId={highlightedId}
            onSelectNode={(n) => setSelection({ type: 'node', data: n })}
            onSelectEdge={(e) => setSelection({ type: 'edge', data: e })}
            onCyReady={() => {}}
          />
        </div>
        <DetailPanel lang={lang} selection={selection} />
      </div>
    </div>
  )
}
