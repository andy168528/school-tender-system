import type { Meta } from '../types'
import { Card } from '../components/ui'
import { fmtTime } from '../util'

const MODE: Record<string, string> = { bootstrap: '首次建立', daily: '每日監測', full: '每週全面掃描' }

export default function AboutPage({ meta, counts }: { meta: Meta; counts: { schools: number; monitored: number; unmonitored: number; tenders: number } }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-5">
        <h2 className="text-lg font-semibold text-slate-800">系統如何運作</h2>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-relaxed text-slate-600">
          <li>學校名單來自教育局公開資料，共 <b>{counts.schools}</b> 間（中學、小學、特殊學校、幼稚園等），每日自動同步。</li>
          <li>程式讀取每間學校網站的首頁及內頁，找出「招標、報價、標書、Tender、Quotation」等欄目。找到的 <b>{counts.monitored}</b> 間列入「監測中學校」，其餘 <b>{counts.unmonitored}</b> 間列入「無法監測學校」並註明原因。</li>
          <li><b>每日香港時間上午 8:00 開始</b>自動檢查所有監測中的招標頁，新公告會標示「新」，並排在「招標公告」表的最前面。</li>
          <li>每週日全面重新掃描所有學校網站。學校網站改版或新增招標頁，都會自動更新。</li>
          <li>程式會打開公告的 PDF 或網頁，讀出截標日期及公告日期，並按標題判斷工程種類。</li>
          <li>公告連續 3 次在學校網站上找不到，會標示「已下架」。</li>
        </ol>
      </Card>
      <Card className="p-5">
        <h2 className="text-lg font-semibold text-slate-800">使用須知</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-slate-600">
          <li><b>截標日期由程式自動讀取</b>，可能讀錯或讀不到（例如掃描版 PDF）。投標前請打開原文件核對。</li>
          <li><b>未截標</b>：截標日期在今日或之後。<b>已截標</b>：截標日期已過。<b>可能已截標</b>：讀不到截標日期，但公告超過 60 日。<b>截標日期不明</b>：讀不到截標日期，需打開文件查看。</li>
          <li>工程種類按標題及文件開頭的關鍵字判斷。已排除電腦、影印機、網站等「保養」服務，但仍可能有少量錯判。取消勾選「只顯示工程相關」可以查看全部公告。</li>
          <li>「首次掃描已存在」表示系統建立時，公告已在學校網站上。之後新發現的公告會顯示發現日期。</li>
          <li>「無法監測」不代表學校沒有招標，只是程式讀不到。可以按學校網站人手查看。</li>
        </ul>
      </Card>
      <Card className="p-5 lg:col-span-2">
        <h2 className="text-lg font-semibold text-slate-800">最近執行紀錄</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left text-xs font-semibold text-slate-600">
              <tr><th className="px-3 py-2">時間</th><th className="px-3 py-2">類型</th><th className="px-3 py-2">檢查網站</th><th className="px-3 py-2">成功讀取</th><th className="px-3 py-2">新公告</th><th className="px-3 py-2">其中工程</th><th className="px-3 py-2">用時</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {meta.runs.map(r => (
                <tr key={r.at}><td className="px-3 py-2">{fmtTime(r.at)}</td><td className="px-3 py-2">{MODE[r.mode] || r.mode}</td><td className="px-3 py-2">{r.sites_checked}</td><td className="px-3 py-2">{r.ok}</td><td className="px-3 py-2">{r.new_tenders}</td><td className="px-3 py-2">{r.new_eng}</td><td className="px-3 py-2">{Math.round(r.seconds / 60)} 分鐘</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
