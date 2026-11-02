import type { ReactNode } from 'react'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>{children}</div>
}

export function Stat({ label, value, hint, tone = 'slate', onClick }: { label: string; value: ReactNode; hint?: string; tone?: 'slate' | 'brand' | 'green' | 'amber'; onClick?: () => void }) {
  const c = { slate: 'text-slate-900', brand: 'text-brand', green: 'text-emerald-600', amber: 'text-amber-600' }[tone]
  return (
    <Card className={`p-4 ${onClick ? 'cursor-pointer hover:border-brand' : ''}`}>
      <div onClick={onClick}>
        <div className="text-xs font-medium text-slate-500">{label}</div>
        <div className={`mt-1 text-2xl font-bold ${c}`}>{value}</div>
        {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
      </div>
    </Card>
  )
}

const BADGE: Record<string, string> = {
  red: 'bg-red-100 text-red-700 ring-red-200', green: 'bg-emerald-100 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-100 text-amber-800 ring-amber-200', slate: 'bg-slate-100 text-slate-600 ring-slate-200',
  blue: 'bg-sky-100 text-sky-700 ring-sky-200', brand: 'bg-brand text-white ring-brand',
}
export function Badge({ children, tone = 'slate' }: { children: ReactNode; tone?: keyof typeof BADGE }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${BADGE[tone]}`}>{children}</span>
}

export function ExtLink({ href, children, className = '' }: { href?: string; children: ReactNode; className?: string }) {
  if (!href) return <span className="text-slate-300">—</span>
  return <a href={href} target="_blank" rel="noreferrer" className={`text-sky-700 hover:text-brand hover:underline ${className}`}>{children}</a>
}

export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="relative">
      <svg className="pointer-events-none absolute left-3 top-2.5 h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 3.4 9.83l3.63 3.64a.75.75 0 1 0 1.06-1.06l-3.63-3.64A5.5 5.5 0 0 0 9 3.5zM5 9a4 4 0 1 1 8 0 4 4 0 0 1-8 0z" clipRule="evenodd" /></svg>
      <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-10 pr-8 text-sm shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand" />
      {value && <button onClick={() => onChange('')} className="absolute right-2 top-2 text-slate-400 hover:text-slate-600">✕</button>}
    </div>
  )
}

export function Pager({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (p: number) => void }) {
  if (pages <= 1) return <div className="px-4 py-3 text-xs text-slate-500">共 {total} 項</div>
  return (
    <div className="flex items-center justify-between px-4 py-3 text-sm">
      <span className="text-xs text-slate-500">共 {total} 項</span>
      <div className="flex items-center gap-2">
        <button disabled={page <= 1} onClick={() => onPage(page - 1)} className="rounded border px-3 py-1 disabled:opacity-40 hover:border-brand">上一頁</button>
        <span className="text-slate-600">{page} / {pages}</span>
        <button disabled={page >= pages} onClick={() => onPage(page + 1)} className="rounded border px-3 py-1 disabled:opacity-40 hover:border-brand">下一頁</button>
      </div>
    </div>
  )
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex cursor-pointer select-none items-center gap-2 text-sm text-slate-700">
      <input type="checkbox" className="h-4 w-4 accent-brand" checked={checked} onChange={e => onChange(e.target.checked)} />
      {label}
    </label>
  )
}

export function Segmented<T extends string>({ label, options, value, onChange }: { label: string; options: T[]; value: T; onChange: (v: T) => void }) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-slate-500">{label}</div>
      <select value={value} onChange={e => onChange(e.target.value as T)}
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand focus:outline-none">
        {options.map(o => <option key={o}>{o}</option>)}
      </select>
    </div>
  )
}
