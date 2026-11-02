export const NON_ENG = '非工程（服務／物品）'

export function todayHK(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
}
export function addDays(iso: string, n: number): string {
  const d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10)
}
export function diffDays(a: string, b: string): number {
  return Math.round((Date.parse(a + 'T00:00:00Z') - Date.parse(b + 'T00:00:00Z')) / 86400000)
}
export function fmtTime(iso?: string): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 16)
}
export function uniq<T>(xs: T[]): T[] { return [...new Set(xs)] }
export function countBy<T>(xs: T[], f: (x: T) => string | string[]): Record<string, number> {
  const c: Record<string, number> = {}
  for (const x of xs) for (const k of ([] as string[]).concat(f(x))) c[k] = (c[k] || 0) + 1
  return c
}
export function matches(q: string, ...fields: (string | undefined)[]): boolean {
  if (!q) return true
  const hay = fields.join(' ').toLowerCase()
  return q.toLowerCase().split(/\s+/).filter(Boolean).every(w => hay.includes(w))
}
export function inSel(sel: string[], v: string | string[]): boolean {
  if (!sel.length) return true
  return ([] as string[]).concat(v).some(x => sel.includes(x))
}
export function host(url: string): string {
  try { return new URL(url).host.replace(/^www\./, '') } catch { return url }
}
export function downloadCSV(name: string, header: string[], rows: (string | number)[][]) {
  const esc = (v: string | number) => '"' + String(v ?? '').replace(/"/g, '""') + '"'
  const csv = '\ufeff' + [header, ...rows].map(r => r.map(esc).join(',')).join('\r\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  a.download = name; a.click(); URL.revokeObjectURL(a.href)
}
const TYPE_ORDER = ['中學', '小學', '特殊學校', '幼稚園', '幼稚園暨幼兒中心', '國際學校（中學）', '國際學校（小學）']
export function sortTypes(xs: string[]): string[] {
  const i = (x: string) => { const n = TYPE_ORDER.indexOf(x); return n < 0 ? 99 : n }
  return [...xs].sort((a, b) => i(a) - i(b) || a.localeCompare(b, 'zh-HK'))
}
