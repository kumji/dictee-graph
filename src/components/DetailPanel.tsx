import type { GraphEdge, GraphNode, Lang } from '../lib/types'
import { GROUP_COLORS } from '../lib/graphStyles'

interface Props {
  lang: Lang
  selection: { type: 'node'; data: GraphNode } | { type: 'edge'; data: GraphEdge } | null
}

export default function DetailPanel({ lang, selection }: Props) {
  if (!selection) {
    return (
      <aside className="w-80 shrink-0 border-l border-gray-200 bg-white p-4 text-sm text-gray-400">
        노드나 엣지를 클릭하면 상세 정보가 여기 표시됩니다.
      </aside>
    )
  }

  if (selection.type === 'node') {
    const n = selection.data
    const label = lang === 'en' ? n.label_en : n.label_ko || n.label_en
    return (
      <aside className="w-80 shrink-0 overflow-y-auto border-l border-gray-200 bg-white p-4">
        <span
          className="inline-block rounded px-2 py-0.5 text-xs font-medium text-white"
          style={{ backgroundColor: GROUP_COLORS[n.group] ?? '#6B7280' }}
        >
          {n.group}
        </span>
        <h2 className="mt-2 text-lg font-semibold text-gray-900">{label}</h2>
        {n.description && <p className="mt-2 text-sm text-gray-600">{n.description}</p>}
        <dl className="mt-4 space-y-2 text-sm">
          <div>
            <dt className="font-medium text-gray-500">Evidence Type</dt>
            <dd className="text-gray-800">{n.evidenceType || '미기재'}</dd>
          </div>
          <div>
            <dt className="font-medium text-gray-500">Page Reference</dt>
            <dd className="text-gray-800">{n.pageReferences || '—'}</dd>
          </div>
          <div>
            <dt className="font-medium text-gray-500">Chapter(s)</dt>
            <dd className="text-gray-800">{n.chapters.join(', ') || '—'}</dd>
          </div>
          <div>
            <dt className="font-medium text-gray-500">Wikibase</dt>
            <dd>
              {n.wikibaseUrl ? (
                <a
                  href={n.wikibaseUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 underline"
                >
                  {n.wikibaseUrl}
                </a>
              ) : (
                <span className="inline-block rounded bg-gray-200 px-2 py-0.5 text-xs text-gray-600">
                  Wikibase 미등록
                </span>
              )}
            </dd>
          </div>
        </dl>
      </aside>
    )
  }

  const e = selection.data
  return (
    <aside className="w-80 shrink-0 overflow-y-auto border-l border-gray-200 bg-white p-4">
      <h2 className="text-lg font-semibold text-gray-900">{e.predicate}</h2>
      <p className="mt-1 text-xs text-gray-500">
        {e.source} → {e.target}
      </p>
      {e.note && <p className="mt-2 text-sm text-gray-600">{e.note}</p>}
      <dl className="mt-4 space-y-2 text-sm">
        <div>
          <dt className="font-medium text-gray-500">Page Ref</dt>
          <dd className="text-gray-800">{e.pageRef || '—'}</dd>
        </div>
        <div>
          <dt className="font-medium text-gray-500">Status</dt>
          <dd className="text-gray-800">{e.status || '—'}</dd>
        </div>
      </dl>
    </aside>
  )
}
