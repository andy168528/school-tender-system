import { useEffect, useMemo, useState } from 'react'
import type { School, Site } from '../types'
import MultiSelect from '../components/MultiSelect'
import { Badge, Card, ExtLink, Pager, SearchBox } from '../components/ui'
import { countBy, fmtTime, host, inSel, matches, sortTypes } from '../util'

export interface MonRow { school: School; site: Site; engCount: number; total: number }
const CONF = ['高', '中', '低']
const CONF_TXT: Record<string, string> = { 高: '高・有招標專頁', 中: '中・公告混在其他頁', 低: '低・只見招標字眼' }
const PAGE = 50

export default function MonitoredPage({ rows }: { rows: MonRow[] }) {
  const [q, setQ] = useState('')
  const [types, setTypes] = useState<string[]>([])
  const [districts, setDistricts] = useState<string[]>([])
  const [conf, setConf] = useState<string[]>([])
  const [finance, setFinance] = useState<string[]>([])
  const [page, setPage] = useState(1)

  const filtered = useMemo(() => rows.filter(r =>
    matches(q, r.school.name, r.school.name_en, r.school.district, r.school.address, r.site.site, r.site.monitor_label)
    && inSel(types, r.school.type) && inSel(districts, r.school.district) && inSel(finance, r.school.finance)
    && inSel(conf, r.site.confidence || '')
  ).sort((a, b) => b.engCount - a.engCount || a.school.name.localeCompare(b.school.name, 'zh-HK')), [rows, q, types, districts, conf, finance])
  useEffect(() => setPage(1), [filtered])

  const o = useMemo(() => ({
    types: sortTypes([...new Set(rows.map(r => r.school.type))]),
    districts: [...new Set(rows.map(r => r.school.district))].sort((a, b) => a.localeCompare(b, 'zh-HK')),
    finance: [...new Set(rows.map(r => r.school.finance))].sort((a, b) => a.localeCompare(b, 'zh-HK')),
    cT: countBy(rows, r => r.school.type), cD: countBy(rows, r => r.school.district),
    cF: countBy(rows, r => r.school.finance), cC: countBy(rows, r => r.site.confidence || ''),
  }), [rows])

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <p className="mb-3 text-sm text-slate-600">以下學校的網站找到招標／報價位置，系統每日香港時間上午 8:00 開始自動檢查一次，發現新公告會加入「招標公告」頁。</p>
        <SearchBox value={q} onChange={setQ} placeholder="搜尋學校名稱、地區、地址、網址…" />
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <MultiSelect label="學校種類" options={o.types} value={types} onChange={setTypes} counts={o.cT} />
          <MultiSelect label="地區" options={o.districts} value={districts} onChange={setDistricts} counts={o.cD} />
          <MultiSelect label="資助種類" options={o.finance} value={finance} onChange={setFinance} counts={o.cF} />
          <MultiSelect label="可信度" options={CONF} value={conf} onChange={setConf} counts={o.cC} />
        </div>
        <div className="mt-3 text-right text-sm text-slate-500">找到 <b className="text-slate-900">{filtered.length}</b> 間學校</div>
      </Card>
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left text-xs font-semibold text-slate-600">
              <tr><th className="px-3 py-2.5">學校</th><th className="px-3 py-2.5">類型／地區</th><th className="px-3 py-2.5">監測位置</th><th className="px-3 py-2.5">可信度</th><th className="px-3 py-2.5">公告數</th><th className="px-3 py-2.5">最近檢查</th><th className="px-3 py-2.5">學校網站</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.slice((page - 1) * PAGE, page * PAGE).map(r => (
                <tr key={r.school.id} className="align-top hover:bg-slate-50">
                  <td className="min-w-[12rem] px-3 py-3"><div className="font-medium text-slate-900">{r.school.name}</div><div className="text-xs text-slate-400">{r.school.name_en}</div></td>
                  <td className="px-3 py-3"><div className="flex flex-wrap gap-1"><Badge>{r.school.type}</Badge><Badge>{r.school.district}</Badge><Badge>{r.school.finance}</Badge></div></td>
                  <td className="max-w-xs px-3 py-3"><ExtLink href={r.site.monitor_url}>{r.site.monitor_label || '招標頁'}</ExtLink></td>
                  <td className="whitespace-nowrap px-3 py-3"><Badge tone={r.site.confidence === '高' ? 'green' : r.site.confidence === '中' ? 'blue' : 'amber'}>{CONF_TXT[r.site.confidence || ''] || '—'}</Badge></td>
                  <td className="whitespace-nowrap px-3 py-3"><b>{r.engCount}</b> <span className="text-xs text-slate-400">工程 ／ {r.total} 全部</span></td>
                  <td className="whitespace-nowrap px-3 py-3 text-xs">{fmtTime(r.site.last_checked)}{(r.site.fail || 0) > 0 && <div className="mt-1"><Badge tone="amber">上次讀取失敗</Badge></div>}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-xs"><ExtLink href={r.site.site}>{host(r.site.site)}</ExtLink>{r.school.phone && <div className="mt-1 text-slate-500">☎ {r.school.phone}</div>}</td>
                </tr>
              ))}
              {!filtered.length && <tr><td colSpan={7} className="px-3 py-12 text-center text-slate-400">沒有符合條件的學校</td></tr>}
            </tbody>
          </table>
        </div>
        <Pager page={page} pages={Math.ceil(filtered.length / PAGE)} total={filtered.length} onPage={setPage} />
      </Card>
    </div>
  )
}
