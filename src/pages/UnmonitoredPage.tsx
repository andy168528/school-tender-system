import { useEffect, useMemo, useState } from 'react'
import type { School, Site } from '../types'
import MultiSelect from '../components/MultiSelect'
import { Badge, Card, ExtLink, Pager, SearchBox } from '../components/ui'
import { countBy, fmtTime, host, inSel, matches, sortTypes } from '../util'

export interface UnRow { school: School; site?: Site; reason: string }
export const REASONS: { key: string; desc: string; tone: 'slate' | 'amber' | 'red' | 'blue' }[] = [
  { key: '未找到招標資訊', tone: 'slate', desc: '網站讀得到，但首頁及內頁兩層都找不到招標／報價字眼。學校可能不在網上刊登，或放在更深的頁面，或公告是圖片。' },
  { key: '網站拒絕程式讀取', tone: 'amber', desc: '網站有防機械人保護（多數是 Cloudflare），拒絕程式讀取。日後改在香港網絡執行，或可讀回部分。' },
  { key: '網站無法連線', tone: 'red', desc: '網站打不開、逾時或網址已失效。' },
  { key: '名單無網址', tone: 'blue', desc: '教育局名單沒有提供這間學校的網址。' },
  { key: '尚未掃描', tone: 'slate', desc: '新加入名單的學校，下次每週全面掃描時會處理。' },
]
const PAGE = 50
const NO_SPONSOR = '未有資料'
const sponsorOf = (s: School) => s.sponsor || NO_SPONSOR

export default function UnmonitoredPage({ rows, watchedSponsors }: { rows: UnRow[]; watchedSponsors: Set<string> }) {
  const [q, setQ] = useState('')
  const [reasons, setReasons] = useState<string[]>([])
  const [types, setTypes] = useState<string[]>([])
  const [districts, setDistricts] = useState<string[]>([])
  const [sponsors, setSponsors] = useState<string[]>([])
  const [page, setPage] = useState(1)

  const filtered = useMemo(() => rows.filter(r =>
    matches(q, r.school.name, r.school.name_en, r.school.district, r.school.address, r.school.website, r.school.sponsor)
    && inSel(reasons, r.reason) && inSel(types, r.school.type) && inSel(districts, r.school.district) && inSel(sponsors, sponsorOf(r.school))
  ), [rows, q, reasons, types, districts, sponsors])
  useEffect(() => setPage(1), [filtered])

  const o = useMemo(() => ({
    types: sortTypes([...new Set(rows.map(r => r.school.type))]),
    districts: [...new Set(rows.map(r => r.school.district))].sort((a, b) => a.localeCompare(b, 'zh-HK')),
    cS: countBy(rows, r => sponsorOf(r.school)),
    cR: countBy(rows, r => r.reason), cT: countBy(rows, r => r.school.type), cD: countBy(rows, r => r.school.district),
  }), [rows])
  const sponsorOpts = useMemo(() => Object.keys(o.cS).sort((a, b) => (a === NO_SPONSOR ? 1 : 0) - (b === NO_SPONSOR ? 1 : 0) || o.cS[b] - o.cS[a] || a.localeCompare(b, 'zh-HK')), [o])
  const tone = (k: string) => REASONS.find(x => x.key === k)?.tone || 'slate'

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h2 className="font-semibold text-slate-800">為何這些學校無法自動監測？</h2>
        <p className="mt-1 text-sm text-slate-500">以下學校仍保留在系統內，可按學校網站人手查看。每週全面重新掃描一次，找到招標頁的學校會自動移到「監測中學校」。</p>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {REASONS.filter(r => o.cR[r.key]).map(r => (
            <button key={r.key} onClick={() => setReasons(reasons.includes(r.key) ? reasons.filter(x => x !== r.key) : [...reasons, r.key])}
              className={`rounded-lg border p-3 text-left transition hover:border-brand ${reasons.includes(r.key) ? 'border-brand bg-brand-light' : 'border-slate-200'}`}>
              <div className="flex items-center justify-between"><Badge tone={r.tone}>{r.key}</Badge><span className="text-lg font-bold text-slate-800">{o.cR[r.key]}</span></div>
              <p className="mt-2 text-xs leading-relaxed text-slate-500">{r.desc}</p>
            </button>
          ))}
        </div>
      </Card>
      <Card className="p-4">
        <SearchBox value={q} onChange={setQ} placeholder="搜尋學校名稱、辦學團體、地區、地址、網址…" />
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <MultiSelect label="原因" options={REASONS.map(r => r.key).filter(k => o.cR[k])} value={reasons} onChange={setReasons} counts={o.cR} />
          <MultiSelect label="學校種類" options={o.types} value={types} onChange={setTypes} counts={o.cT} />
          <MultiSelect label="地區" options={o.districts} value={districts} onChange={setDistricts} counts={o.cD} />
          <MultiSelect label="辦學團體" options={sponsorOpts} value={sponsors} onChange={setSponsors} counts={o.cS} />
        </div>
        <div className="mt-3 text-right text-sm text-slate-500">找到 <b className="text-slate-900">{filtered.length}</b> 間學校</div>
      </Card>
      <Card className="overflow-hidden">
        <ul className="divide-y divide-slate-100 md:hidden">
          {filtered.slice((page - 1) * PAGE, page * PAGE).map(r => (
            <li key={r.school.id} className="p-4">
              <div className="font-semibold text-slate-900">{r.school.name}</div>
              <div className="text-xs text-slate-400">{r.school.name_en}</div>
              {r.school.sponsor && <div className="mt-1 text-xs text-slate-600">辦學團體：{r.school.sponsor}{r.school.sponsor_src === '按校名推斷' && <span className="text-slate-400">（按校名推斷）</span>}{watchedSponsors.has(r.school.sponsor) && <span className="ml-1 text-green-700">・團體招標頁監測中</span>}</div>}
              <div className="mt-1.5 flex flex-wrap gap-1"><Badge tone={tone(r.reason)}>{r.reason}</Badge><Badge>{r.school.type}</Badge><Badge>{r.school.district}</Badge>
                {r.site?.last_ok && <Badge tone="green">曾成功讀取</Badge>}</div>
              {r.site?.error && <div className="mt-1 break-all text-xs text-slate-400">{r.site.error}</div>}
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                {r.school.website && <ExtLink href={r.school.website}>{host(r.school.website)}</ExtLink>}
                {r.school.phone && <a href={'tel:' + r.school.phone.replace(/\s/g, '')} className="text-slate-600">☎ {r.school.phone}</a>}
                {r.site?.last_checked && <span className="text-xs text-slate-400">最近檢查 {fmtTime(r.site.last_checked)}</span>}
              </div>
            </li>
          ))}
          {!filtered.length && <li className="px-3 py-12 text-center text-slate-400">沒有符合條件的學校</li>}
        </ul>
        <div className="hidden overflow-x-auto md:block">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left text-xs font-semibold text-slate-600">
              <tr><th className="px-3 py-2.5">學校</th><th className="px-3 py-2.5">辦學團體</th><th className="px-3 py-2.5">類型／地區</th><th className="px-3 py-2.5">無法監測原因</th><th className="px-3 py-2.5">學校網站</th><th className="px-3 py-2.5">最近檢查</th><th className="px-3 py-2.5">曾成功讀取</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.slice((page - 1) * PAGE, page * PAGE).map(r => (
                <tr key={r.school.id} className="align-top hover:bg-slate-50">
                  <td className="min-w-[12rem] px-3 py-3"><div className="font-medium text-slate-900">{r.school.name}</div><div className="text-xs text-slate-400">{r.school.name_en}</div></td>
                  <td className="min-w-[8rem] px-3 py-3 text-xs text-slate-700">{r.school.sponsor || <span className="text-slate-300">—</span>}{r.school.sponsor_src === '按校名推斷' && <div className="text-slate-400">按校名推斷</div>}{r.school.sponsor && watchedSponsors.has(r.school.sponsor) && <div className="text-green-700">團體招標頁監測中</div>}</td>
                  <td className="px-3 py-3"><div className="flex flex-wrap gap-1"><Badge>{r.school.type}</Badge><Badge>{r.school.district}</Badge></div></td>
                  <td className="whitespace-nowrap px-3 py-3"><Badge tone={tone(r.reason)}>{r.reason}</Badge>{r.site?.error && <div className="mt-1 max-w-[14rem] truncate text-xs text-slate-400" title={r.site.error}>{r.site.error}</div>}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-xs"><ExtLink href={r.school.website || undefined}>{r.school.website ? host(r.school.website) : ''}</ExtLink>{r.school.phone && <div className="mt-1 text-slate-500">☎ {r.school.phone}</div>}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-xs">{fmtTime(r.site?.last_checked)}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-xs">{r.site?.last_ok ? <Badge tone="green">是</Badge> : <Badge>否</Badge>}</td>
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
