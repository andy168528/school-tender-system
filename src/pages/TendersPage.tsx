import { useMemo, useState, useEffect } from 'react'
import type { TenderRow, Meta } from '../types'
import MultiSelect from '../components/MultiSelect'
import { Badge, Card, ExtLink, Pager, SearchBox, Segmented, Stat, Toggle } from '../components/ui'
import { NON_ENG, addDays, countBy, downloadCSV, inSel, matches, sortTypes, todayHK, fmtTime } from '../util'

const STATUSES = ['未截標', '已截標', '可能已截標', '截標日期不明']
const ENG_ORDER = ['樓宇維修保養', '機電工程 (E&M)', '水電維修', '小型工程 (Minor Works)', '改建加建 / 裝修 (A&A)', '樓宇檢查 / 測試', '滲水 / 防水', '其他工程', NON_ENG]
const DATE_OPTS = ['全部日期', '近 7 日', '近 30 日', '近 90 日', '近 1 年'] as const
const NEW_OPTS = ['全部', '今日新增', '近 7 日新增'] as const
const SORT_OPTS = ['最新公告優先', '截標日期（最近先）', '學校名稱'] as const
const PAGE = 50

function statusBadge(r: TenderRow) {
  if (r.status === '未截標') return <Badge tone="green">未截標{r.daysLeft !== undefined && (r.daysLeft === 0 ? '・今日截標' : `・剩 ${r.daysLeft} 日`)}</Badge>
  if (r.status === '已截標') return <Badge tone="slate">已截標</Badge>
  if (r.status === '可能已截標') return <Badge tone="amber">可能已截標</Badge>
  return <Badge tone="blue">截標日期不明</Badge>
}

export default function TendersPage({ rows, meta, monitoredSchools }: { rows: TenderRow[]; meta: Meta; monitoredSchools: number }) {
  const [q, setQ] = useState('')
  const [types, setTypes] = useState<string[]>([])
  const [districts, setDistricts] = useState<string[]>([])
  const [eng, setEng] = useState<string[]>([])
  const [status, setStatus] = useState<string[]>([])
  const [finance, setFinance] = useState<string[]>([])
  const [dateOpt, setDateOpt] = useState<typeof DATE_OPTS[number]>('全部日期')
  const [newOpt, setNewOpt] = useState<typeof NEW_OPTS[number]>('全部')
  const [sort, setSort] = useState<typeof SORT_OPTS[number]>('最新公告優先')
  const [engOnly, setEngOnly] = useState(true)
  const [showGone, setShowGone] = useState(false)
  const [pdfOnly, setPdfOnly] = useState(false)
  const [page, setPage] = useState(1)
  const today = todayHK()

  const base = useMemo(() => rows.filter(r => (showGone || r.active) && (!engOnly || r.eng_types.length > 0)), [rows, showGone, engOnly])

  const filtered = useMemo(() => {
    const from = { '全部日期': '', '近 7 日': addDays(today, -7), '近 30 日': addDays(today, -30), '近 90 日': addDays(today, -90), '近 1 年': addDays(today, -365) }[dateOpt]
    const out = base.filter(r => {
      const ss = r.schools
      return matches(q, r.title, r.url, r.site, ...ss.flatMap(s => [s.name, s.name_en, s.district, s.address]))
        && inSel(types, ss.map(s => s.type)) && inSel(districts, ss.map(s => s.district)) && inSel(finance, ss.map(s => s.finance))
        && inSel(eng, r.types) && inSel(status, r.status)
        && (!from || r.date >= from)
        && (newOpt === '全部' || (newOpt === '今日新增' ? r.isToday : r.isNew))
        && (!pdfOnly || r.doc)
    })
    const name = (r: TenderRow) => r.school?.name || r.site
    if (sort === '最新公告優先') out.sort((a, b) => Number(b.isNew) - Number(a.isNew) || b.date.localeCompare(a.date) || b.first_seen.localeCompare(a.first_seen))
    else if (sort === '截標日期（最近先）') out.sort((a, b) => {
      const k = (r: TenderRow) => r.status === '未截標' ? '0' + r.deadline : r.deadline ? '1' + (9e8 - Date.parse(r.deadline) / 1e5) : '2'
      return k(a).localeCompare(k(b)) || b.date.localeCompare(a.date)
    })
    else out.sort((a, b) => name(a).localeCompare(name(b), 'zh-HK'))
    return out
  }, [base, q, types, districts, finance, eng, status, dateOpt, newOpt, sort, pdfOnly, today])

  useEffect(() => setPage(1), [filtered])

  const opts = useMemo(() => ({
    types: sortTypes([...new Set(base.flatMap(r => r.schools.map(s => s.type)))]),
    districts: [...new Set(base.flatMap(r => r.schools.map(s => s.district)))].sort((a, b) => a.localeCompare(b, 'zh-HK')),
    finance: [...new Set(base.flatMap(r => r.schools.map(s => s.finance)))].sort((a, b) => a.localeCompare(b, 'zh-HK')),
    eng: ENG_ORDER.filter(e => base.some(r => r.types.includes(e))),
    cType: countBy(base, r => [...new Set(r.schools.map(s => s.type))]),
    cDist: countBy(base, r => [...new Set(r.schools.map(s => s.district))]),
    cFin: countBy(base, r => [...new Set(r.schools.map(s => s.finance))]),
    cEng: countBy(base, r => r.types), cStatus: countBy(base, r => r.status),
  }), [base])

  const engRows = rows.filter(r => r.active && r.eng_types.length)
  const openEng = engRows.filter(r => r.status === '未截標').length
  const newWeek = rows.filter(r => r.isNew && r.eng_types.length).length
  const lastRun = meta.runs[0]
  const anyFilter = q || types.length || districts.length || eng.length || status.length || finance.length || dateOpt !== '全部日期' || newOpt !== '全部' || pdfOnly
  const reset = () => { setQ(''); setTypes([]); setDistricts([]); setEng([]); setStatus([]); setFinance([]); setDateOpt('全部日期'); setNewOpt('全部'); setPdfOnly(false) }
  const pageRows = filtered.slice((page - 1) * PAGE, page * PAGE)

  const exportCSV = () => downloadCSV(`學校工程招標_${today}.csv`,
    ['學校', '學校類型', '地區', '公告標題', '工程種類', '公告日期', '截標日期', '截標狀態', '公告連結', '招標頁', '首次發現'],
    filtered.map(r => [r.schools.map(s => s.name).join(' / '), r.school?.type || '', r.school?.district || '', r.title, r.types.join('、'),
      r.published || '', r.deadline || '', r.status, r.url, r.page, r.baseline ? '首次掃描' : r.first_seen]))

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="未截標工程招標" value={openEng} tone="green" hint="有截標日期而未過期" onClick={() => { reset(); setStatus(['未截標']) }} />
        <Stat label="近 7 日新發現（工程）" value={newWeek} tone="brand" hint="首次掃描之後的新公告" onClick={() => { reset(); setNewOpt('近 7 日新增') }} />
        <Stat label="網站上的工程公告" value={engRows.length} hint="仍在學校網站上" />
        <Stat label="監測中學校" value={monitoredSchools} hint={`最近更新：${fmtTime(meta.updated_at)}`} />
      </div>

      <Card className="p-4">
        <div className="grid gap-3 md:grid-cols-[1fr_auto]">
          <SearchBox value={q} onChange={setQ} placeholder="搜尋學校名稱、公告標題、地區、地址、網址… (可輸入多個字詞，以空格分隔)" />
          <div className="flex items-center gap-2">
            <button onClick={exportCSV} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm hover:border-brand hover:text-brand">匯出 Excel (CSV)</button>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          <MultiSelect label="學校種類" options={opts.types} value={types} onChange={setTypes} counts={opts.cType} />
          <MultiSelect label="地區" options={opts.districts} value={districts} onChange={setDistricts} counts={opts.cDist} />
          <MultiSelect label="工程種類" options={opts.eng} value={eng} onChange={setEng} counts={opts.cEng} />
          <MultiSelect label="截標狀態" options={STATUSES} value={status} onChange={setStatus} counts={opts.cStatus} />
          <MultiSelect label="資助種類" options={opts.finance} value={finance} onChange={setFinance} counts={opts.cFin} />
          <Segmented label="公告日期" options={[...DATE_OPTS]} value={dateOpt} onChange={setDateOpt} />
          <Segmented label="新公告" options={[...NEW_OPTS]} value={newOpt} onChange={setNewOpt} />
          <Segmented label="排序" options={[...SORT_OPTS]} value={sort} onChange={setSort} />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2">
          <Toggle checked={engOnly} onChange={setEngOnly} label="只顯示工程相關" />
          <Toggle checked={pdfOnly} onChange={setPdfOnly} label="只顯示有 PDF／附件" />
          <Toggle checked={showGone} onChange={setShowGone} label="包括已從網站下架的公告" />
          {anyFilter ? <button onClick={reset} className="text-sm text-brand hover:underline">清除所有篩選</button> : null}
          <span className="ml-auto text-sm text-slate-500">找到 <b className="text-slate-900">{filtered.length}</b> 條公告</span>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left text-xs font-semibold text-slate-600">
              <tr>
                <th className="px-3 py-2.5">公告日期</th>
                <th className="px-3 py-2.5">學校</th>
                <th className="px-3 py-2.5">公告標題</th>
                <th className="px-3 py-2.5">工程種類</th>
                <th className="px-3 py-2.5">截標日期</th>
                <th className="px-3 py-2.5">連結</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {pageRows.map(r => (
                <tr key={r.id} className={`align-top hover:bg-slate-50 ${!r.active ? 'opacity-60' : ''}`}>
                  <td className="whitespace-nowrap px-3 py-3">
                    <div className="font-medium text-slate-800">{r.published || '—'}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {r.isToday ? <Badge tone="brand">今日新增</Badge> : r.isNew ? <Badge tone="red">新</Badge> : null}
                      {!r.active && <Badge>已下架</Badge>}
                    </div>
                    <div className="mt-1 text-xs text-slate-400">{r.baseline ? '首次掃描已存在' : `發現於 ${r.first_seen}`}</div>
                  </td>
                  <td className="min-w-[12rem] px-3 py-3">
                    <div className="font-medium text-slate-900">{r.school?.name || r.site}</div>
                    {r.schools.length > 1 && <div className="text-xs text-slate-500" title={r.schools.map(s => s.name).join('\n')}>＋同網站另 {r.schools.length - 1} 間學校</div>}
                    <div className="mt-1 flex flex-wrap gap-1">
                      {r.school && <Badge>{r.school.type}</Badge>}
                      {r.school && <Badge>{r.school.district}</Badge>}
                    </div>
                  </td>
                  <td className="min-w-[16rem] max-w-md px-3 py-3">
                    <ExtLink href={r.url} className="font-medium">{r.title}</ExtLink>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex max-w-[12rem] flex-wrap gap-1">
                      {r.types.map(t => <Badge key={t} tone={t === NON_ENG ? 'slate' : 'blue'}>{t}</Badge>)}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-3">
                    <div className="font-medium text-slate-800">{r.deadline || '—'}</div>
                    <div className="mt-1">{statusBadge(r)}</div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-xs">
                    <div className="flex flex-col gap-1">
                      <ExtLink href={r.url}>{r.doc ? '📄 PDF／附件' : '🔗 公告'}</ExtLink>
                      <ExtLink href={r.page}>招標頁</ExtLink>
                      <ExtLink href={r.site}>學校網站</ExtLink>
                    </div>
                  </td>
                </tr>
              ))}
              {!pageRows.length && <tr><td colSpan={6} className="px-3 py-12 text-center text-slate-400">沒有符合條件的公告</td></tr>}
            </tbody>
          </table>
        </div>
        <Pager page={page} pages={Math.ceil(filtered.length / PAGE)} total={filtered.length} onPage={p => { setPage(p); window.scrollTo({ top: 0, behavior: 'smooth' }) }} />
      </Card>
      {lastRun && <p className="text-xs text-slate-400">上次執行：{fmtTime(lastRun.at)}，檢查 {lastRun.sites_checked} 個網站，新增 {lastRun.new_tenders} 條公告（工程 {lastRun.new_eng} 條）。截標日期由程式從標題或 PDF 自動讀取，投標前請以原文件為準。</p>}
    </div>
  )
}
