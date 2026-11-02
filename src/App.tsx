import { useEffect, useMemo, useState } from 'react'
import type { Data } from './types'
import { buildRows, loadData, schoolsBySite } from './data'
import TendersPage from './pages/TendersPage'
import MonitoredPage, { type MonRow } from './pages/MonitoredPage'
import UnmonitoredPage, { type UnRow } from './pages/UnmonitoredPage'
import AboutPage from './pages/AboutPage'
import { fmtTime } from './util'

const TABS = [
  { id: 'tenders', label: '招標公告' },
  { id: 'monitored', label: '監測中學校' },
  { id: 'unmonitored', label: '無法監測學校' },
  { id: 'about', label: '系統說明' },
] as const
type Tab = typeof TABS[number]['id']
const curTab = (): Tab => (TABS.find(t => '#' + t.id === location.hash)?.id || 'tenders')

export default function App() {
  const [data, setData] = useState<Data | null>(null)
  const [err, setErr] = useState('')
  const [tab, setTab] = useState<Tab>(curTab())
  useEffect(() => { loadData().then(setData).catch(e => setErr(String(e))) }, [])
  useEffect(() => { const h = () => setTab(curTab()); window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h) }, [])

  const derived = useMemo(() => {
    if (!data) return null
    const bySite = schoolsBySite(data.schools)
    const siteMap = new Map(data.sites.map(s => [s.site, s]))
    const rows = buildRows(data.tenders, bySite)
    const eng: Record<string, number> = {}, total: Record<string, number> = {}
    for (const t of data.tenders) { total[t.site] = (total[t.site] || 0) + 1; if (t.eng_types.length) eng[t.site] = (eng[t.site] || 0) + 1 }
    const mon: MonRow[] = [], un: UnRow[] = []
    for (const school of data.schools) {
      const site = school.website ? siteMap.get(school.website) : undefined
      if (site?.monitored) mon.push({ school, site, engCount: eng[site.site] || 0, total: total[site.site] || 0 })
      else un.push({ school, site, reason: !school.website ? '名單無網址' : site?.reason || '尚未掃描' })
    }
    return { rows, mon, un }
  }, [data])

  const counts = { tenders: derived?.rows.filter(r => r.active && r.eng_types.length).length, monitored: derived?.mon.length, unmonitored: derived?.un.length }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-4 px-4 py-3">
          <img src="/logo.png" alt="凱雄工程" className="h-12 w-auto rounded" />
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-slate-900 md:text-xl">凱雄-學校工程自動化招標系統</h1>
            <p className="text-xs text-slate-500">全港學校招標公告每日自動監測・每日上午 8:00 開始更新{data && `・最近更新 ${fmtTime(data.meta.updated_at)}`}</p>
          </div>
        </div>
        <nav className="mx-auto flex max-w-[1500px] gap-1 overflow-x-auto px-4">
          {TABS.map(t => {
            const n = t.id === 'tenders' ? counts.tenders : t.id === 'monitored' ? counts.monitored : t.id === 'unmonitored' ? counts.unmonitored : undefined
            return (
              <a key={t.id} href={'#' + t.id}
                className={`whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition ${tab === t.id ? 'border-brand text-brand' : 'border-transparent text-slate-600 hover:text-slate-900'}`}>
                {t.label}{n !== undefined && <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs ${tab === t.id ? 'bg-brand-light' : 'bg-slate-100'}`}>{n}</span>}
              </a>
            )
          })}
        </nav>
      </header>
      <main className="mx-auto max-w-[1500px] px-4 py-5">
        {err && <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">資料載入失敗：{err}</div>}
        {!data && !err && <div className="py-20 text-center text-slate-400">載入資料中…</div>}
        {data && derived && (
          tab === 'tenders' ? <TendersPage rows={derived.rows} meta={data.meta} monitoredSchools={derived.mon.length} />
            : tab === 'monitored' ? <MonitoredPage rows={derived.mon} />
              : tab === 'unmonitored' ? <UnmonitoredPage rows={derived.un} />
                : <AboutPage meta={data.meta} counts={{ schools: data.schools.length, monitored: derived.mon.length, unmonitored: derived.un.length, tenders: data.tenders.length }} />
        )}
      </main>
      <footer className="py-6 text-center text-xs text-slate-400">© 凱雄工程服務有限公司 Armour Engineering Services Ltd.・學校資料來源：教育局</footer>
    </div>
  )
}
