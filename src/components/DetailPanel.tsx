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
            <dt className="font-medium text-gray-500">외부 권위 연결</dt>
            <dd>
              {n.equivalentUri ? (
                <a
                  href={n.equivalentUri}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 underline"
                >
                  {n.equivalentUri}
                </a>
              ) : (
                <span className="text-gray-500">외부 권위 연결 없음</span>
              )}
            </dd>
          </div>
          {n.broader.length > 0 && (
            <div>
              <dt className="font-medium text-gray-500">Broader</dt>
              <dd className="space-y-1">
                {n.broader.map((uri) => (
                  <a
                    key={uri}
                    href={uri}
                    target="_blank"
                    rel="noreferrer"
                    className="block break-all text-blue-600 underline"
                  >
                    {uri}
                  </a>
                ))}
              </dd>
            </div>
          )}
          {n.closeMatch.length > 0 && (
            <div>
              <dt className="font-medium text-gray-500">Close Match</dt>
              <dd className="space-y-1">
                {n.closeMatch.map((uri) => (
                  <a
                    key={uri}
                    href={uri}
                    target="_blank"
                    rel="noreferrer"
                    className="block break-all text-blue-600 underline"
                  >
                    {uri}
                  </a>
                ))}
              </dd>
            </div>
          )}
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
      {e.schemaViolation && (
        <p className="mt-2 text-xs text-gray-500">
          스키마상 Domain/Range 예외 — 연구자 판단 대기 중인 관계입니다.
        </p>
      )}
    </aside>
  )
}
