import { useEffect, useMemo, useRef, useState } from 'react'

interface Props {
  label: string
  options: string[]
  value: string[]
  onChange: (v: string[]) => void
  counts?: Record<string, number>
}

export default function MultiSelect({ label, options, value, onChange, counts }: Props) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  const shown = useMemo(() => options.filter(o => !q || o.toLowerCase().includes(q.toLowerCase())), [options, q])
  const toggle = (o: string) => onChange(value.includes(o) ? value.filter(x => x !== o) : [...value, o])
  const summary = value.length === 0 ? '全部' : value.length === 1 ? value[0] : `已選 ${value.length} 項`

  return (
    <div className="relative" ref={ref}>
      <div className="mb-1 text-xs font-medium text-slate-500">{label}</div>
      <button type="button" onClick={() => setOpen(!open)}
        className={`flex w-full items-center justify-between gap-2 rounded-lg border bg-white px-3 py-2 text-left text-sm shadow-sm hover:border-brand ${value.length ? 'border-brand text-brand-dark' : 'border-slate-300 text-slate-700'}`}>
        <span className="truncate">{summary}</span>
        <svg className={`h-4 w-4 shrink-0 transition ${open ? 'rotate-180' : ''}`} viewBox="0 0 20 20" fill="currentColor"><path d="M5.3 7.3a1 1 0 0 1 1.4 0L10 10.6l3.3-3.3a1 1 0 1 1 1.4 1.4l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 0 1 0-1.4z" /></svg>
      </button>
      {open && (
        <div className="absolute z-30 mt-1 w-full min-w-[15rem] rounded-lg border border-slate-200 bg-white shadow-lg">
          {options.length > 8 && (
            <div className="border-b p-2">
              <input autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder="搜尋選項…"
                className="w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-brand focus:outline-none" />
            </div>
          )}
          <div className="flex justify-between border-b px-3 py-1.5 text-xs">
            <button className="text-brand hover:underline" onClick={() => onChange([...new Set([...value, ...shown])])}>全選</button>
            <button className="text-slate-500 hover:underline" onClick={() => onChange([])}>清除</button>
          </div>
          <ul className="max-h-72 overflow-auto py-1">
            {shown.map(o => (
              <li key={o}>
                <label className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm hover:bg-slate-50">
                  <input type="checkbox" className="h-4 w-4 accent-brand" checked={value.includes(o)} onChange={() => toggle(o)} />
                  <span className="flex-1">{o}</span>
                  {counts && <span className="text-xs text-slate-400">{counts[o] || 0}</span>}
                </label>
              </li>
            ))}
            {!shown.length && <li className="px-3 py-2 text-sm text-slate-400">沒有選項</li>}
          </ul>
        </div>
      )}
    </div>
  )
}
