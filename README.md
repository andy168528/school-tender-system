# 凱雄-學校工程自動化招標系統

每日自動檢查全港學校網站的招標／報價公告，整理成可搜尋、可篩選的網頁。

## 結構
- `crawler/` — Python 爬蟲
  - `crawl.py`：讀取學校網站，尋找招標頁及公告
  - `pw.py`：用瀏覽器（Playwright）讀取需要執行 JavaScript 的網站
  - `classify.py`：工程種類、截標日期、公告日期判斷
  - `monitor.py`：每日／每週流程，更新 `public/data/*.json`
- `src/` — 網頁介面（React + Vite + Tailwind）
- `public/data/` — 系統資料（學校、網站、公告、執行紀錄）
- `.github/workflows/monitor.yml` — GitHub Actions 定時執行

## 排程
- 每日 08:30（香港時間）：檢查所有監測中的招標頁，約 9:00 前完成
- 每週日 02:00：全面重新掃描所有學校網站
- 亦可在 GitHub → Actions → 「每日監測學校招標」→ Run workflow 手動執行

網頁直接讀取 GitHub 上最新的 `public/data`，所以每日更新後不用重新部署。

## 本機執行
```bash
pip install -r crawler/requirements.txt && python -m playwright install chromium
python crawler/monitor.py daily      # 或 full
npm install && npm run dev
```
