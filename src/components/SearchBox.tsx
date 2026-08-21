import { useMemo, useState } from 'react'
import type { GraphNode, Lang } from '../lib/types'

interface Props {
  nodes: GraphNode[]
  lang: Lang
  onSelect: (node: GraphNode) => void
}

export default function SearchBox({ nodes, lang, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    return nodes
      .filter(
        (n) =>
          n.label_en.toLowerCase().includes(q) || n.label_ko.toLowerCase().includes(q),
      )
      .slice(0, 8)
  }, [query, nodes])

  return (
    <div className="relative w-56">
      <input
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="검색 🔍"
        className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
      />
      {open && results.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full rounded border border-gray-200 bg-white shadow-lg">
          {results.map((n) => (
            <li key={n.id}>
              <button
                className="block w-full px-2 py-1 text-left text-sm hover:bg-gray-100"
                onClick={() => {
                  onSelect(n)
                  setQuery(lang === 'en' ? n.label_en : n.label_ko || n.label_en)
                  setOpen(false)
                }}
              >
                {lang === 'en' ? n.label_en : n.label_ko || n.label_en}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
