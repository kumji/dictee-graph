import { GROUP_COLORS } from '../lib/graphStyles'

interface Props {
  types: string[]
  activeTypes: Set<string>
  onToggleType: (type: string) => void
  chapters: string[]
  activeChapter: string | null
  onChangeChapter: (chapter: string | null) => void
  lang: 'en' | 'ko'
  onToggleLang: () => void
}

export default function FilterBar({
  types,
  activeTypes,
  onToggleType,
  chapters,
  activeChapter,
  onChangeChapter,
  lang,
  onToggleLang,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-4 border-b border-gray-200 bg-white px-4 py-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-gray-500">Type</span>
        {types.map((t) => {
          const active = activeTypes.size === 0 || activeTypes.has(t)
          return (
            <button
              key={t}
              onClick={() => onToggleType(t)}
              className="flex items-center gap-1 rounded-full border px-2 py-0.5"
              style={{
                borderColor: GROUP_COLORS[t] ?? '#6B7280',
                opacity: active ? 1 : 0.35,
              }}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: GROUP_COLORS[t] ?? '#6B7280' }}
              />
              {t}
            </button>
          )
        })}
      </div>

      <div className="flex items-center gap-2">
        <span className="font-medium text-gray-500">Chapter</span>
        <select
          value={activeChapter ?? ''}
          onChange={(evt) => onChangeChapter(evt.target.value || null)}
          className="rounded border border-gray-300 px-2 py-0.5"
        >
          <option value="">전체</option>
          {chapters.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <button
        onClick={onToggleLang}
        className="ml-auto rounded border border-gray-300 px-2 py-0.5 font-medium"
      >
        {lang === 'en' ? 'EN' : 'KO'}
      </button>
    </div>
  )
}
