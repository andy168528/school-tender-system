import type { Data, Meta, School, Site, Tender, TenderRow, DeadlineStatus } from './types'
import { NON_ENG, todayHK, addDays, diffDays } from './util'

const BASES = [import.meta.env.VITE_DATA_BASE as string | undefined, '/data/'].filter(Boolean) as string[]

async function getJSON<T>(name: string): Promise<T> {
  let err: unknown
  for (const b of BASES) {
    try {
      const r = await fetch(b + name + '?v=' + Date.now().toString().slice(0, -5))
      if (r.ok) return await r.json()
      err = new Error(r.status + ' ' + name)
    } catch (e) { err = e }
  }
  throw err
}

export async function loadData(): Promise<Data> {
  const [schools, sites, tenders, meta] = await Promise.all([
    getJSON<School[]>('schools.json'), getJSON<Site[]>('sites.json'),
    getJSON<Tender[]>('tenders.json'), getJSON<Meta>('meta.json'),
  ])
  return { schools, sites, tenders, meta }
}

export function schoolsBySite(schools: School[]): Map<string, School[]> {
  const m = new Map<string, School[]>()
  for (const s of schools) if (s.website) { const a = m.get(s.website) || []; a.push(s); m.set(s.website, a) }
  return m
}

export function buildRows(tenders: Tender[], bySite: Map<string, School[]>): TenderRow[] {
  const today = todayHK()
  return tenders.map(t => {
    const schools = bySite.get(t.site) || []
    const date = t.published || t.deadline || (t.baseline ? '' : t.first_seen)
    let status: DeadlineStatus; let daysLeft: number | undefined
    if (t.deadline) {
      daysLeft = diffDays(t.deadline, today)
      status = daysLeft >= 0 ? '未截標' : '已截標'
    } else if (t.published && t.published < addDays(today, -60)) status = '可能已截標'
    else status = '截標日期不明'
    const isNew = !t.baseline && t.first_seen >= addDays(today, -7)
    return { ...t, schools, school: schools[0], status, daysLeft, date, isNew, isToday: !t.baseline && t.first_seen === today,
      types: t.eng_types.length ? t.eng_types : [NON_ENG] }
  })
}
