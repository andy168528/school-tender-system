"""Gemini check of each notice: is it a new tender, is it engineering, which types."""
import base64, json, os, re, threading, time, requests, datetime as dt
import classify

KEY = os.environ.get('GEMINI_API_KEY', '').strip()
MODELS = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash-lite,gemini-3.5-flash').split(',')
BUDGET = int(os.environ.get('GEMINI_BUDGET', 20 * 60))
_end = time.time() + BUDGET
RPM = int(os.environ.get('GEMINI_RPM', 14))  # free tier allows 15 requests/min per model
_lock = threading.Lock()
_next = {}
STATS = {'ok': 0, 'limited': 0, 'failed': 0}
_spent = set()  # models whose daily free-tier quota is used up

def available():
    return bool(KEY) and time.time() < _end and any(m.strip() not in _spent for m in MODELS)

def _slot(model):
    with _lock:
        now = time.time(); at = max(now, _next.get(model, 0))
        _next[model] = at + 60 / RPM
    time.sleep(at - now)
TYPES = [n for n, _ in classify.ENG_TYPES] + [classify.OTHER_ENG]

# Bump VERSION whenever SCOPE/PROMPT/eng_scope.md changes: every stored judgement with another version is re-checked.
VERSION = 4
CONFIRM = [m.strip() for m in os.environ.get('GEMINI_CONFIRM_MODEL', 'gemini-3.5-flash').split(',') if m.strip()]

SCOPE = """【算是工程（eng=true）】由承辦商或專業顧問在校舍、斜坡或屋宇設備上進行的建造、維修、改建、安裝、檢查或相關專業服務，按以下專業範疇：
- Builder maintenance works：樓宇維修保養、石屎剝落修補、內外牆翻新油漆、天台防水、門窗、地台、天花、圍欄、訂造及安裝固定木工櫃（即使附帶貼畫）
- E&M works：冷氣／通風、電力及總掣房、照明、消防裝置、升降機、太陽能／光伏、電動車充電設施、發電機、水泵、水喉及渠務
- Architectural works／A&A works：裝修、翻新、改建加建、房間改裝（例如 STEM 室、教員室）、無障礙設施、外牆設計
- Structural works：結構加固、鋼架上蓋、升降機井、地基
- Minor works：小型工程、窗鉸修理、批盪修補、鋁窗花、潔具更換、鋪砌瓷磚
- Building studies：樓宇狀況勘察、斜坡評估、石屎測試、外牆紅外線檢測
- Building surveyor 職務：強制驗樓／驗窗、違建清拆、滲水調查、小型工程監工及申報、合規顧問
- 定期保養服務：升降機保養、清洗冷氣、消防系統保養、駐校技工維修
- 工程顧問／設計服務：建築顧問、工料測量、項目管理、校舍或課室設計
- 兒童遊樂設施、攀石牆、組合屋、帳篷、有蓋設施
- 項目以裝修／建造為主，即使附帶少量設備，仍算工程

【不算工程（eng=false）】即使標題有「工程」二字也不算：
- 壁畫、彩繪、馬賽克、貼畫創作、藝術美化校園、學生工作坊
- 園藝、花圃／草坪保養、平整草坪、種植、溫室／花棚、綠化租賃（即使附帶少量水電配套）
- 只是供應連安裝設備：觸控屏幕、電子白板、LED Wall／顯示屏、投影、音響、廣播（PA）系統、舞台燈光、閉路電視（CCTV）、門禁／保安系統、電腦、AI／體育器材、可移動傢俬
- 網絡工程：光纖、無線網絡（WiFi）、網絡佈線
- 物品採購、IT、交流團、活動、午膳、教學／培訓服務、清潔、保安人員、物業管理、校車、印刷、水質／空氣質素化驗、ESG／ISO 顧問"""

_REF = os.path.join(os.path.dirname(__file__), 'eng_scope.md')
if os.path.exists(_REF): SCOPE += '\n' + open(_REF, encoding='utf-8').read().strip()

PROMPT = """你是香港學校招標公告的分類員。以下是學校網站上的一個連結（標題、檔名及文件開頭內容）。
請判斷：
1. tender：這是否一份「邀請供應商投標／報價」的公告或標書文件？只看文件性質，截標日期已過也算 true。中標結果、中標公司名單、招聘、通告、已批出合約一覽表等都是 false。
2. eng：按以下範圍判斷項目本身是否工程。只看項目內容，不要因為文件內的標準條款（例如「維護國家安全」、「防止賄賂條例」、「校舍」）而判斷為工程。
{scope}
3. types：如 eng 為 true，從以下選一個或多個：{types}
4. summary：用繁體中文一句話（30字內）說明項目內容。
5. reason：用繁體中文一句話說明 eng 的判斷理由，要指出屬於上面哪一類。
6. deadline：文件寫明的截標／截止遞交日期，格式 YYYY-MM-DD；文件沒有寫明就留空，不要估計。
7. published：文件寫明的招標／公告／發出日期，格式 YYYY-MM-DD；沒有寫明就留空。
如有附件 PDF，以附件內容為準。

標題：{title}
網址：{url}
文件內容：
{text}"""

SCHEMA = {'type': 'OBJECT', 'properties': {
    'tender': {'type': 'BOOLEAN'}, 'eng': {'type': 'BOOLEAN'},
    'types': {'type': 'ARRAY', 'items': {'type': 'STRING', 'enum': TYPES}},
    'summary': {'type': 'STRING'}, 'reason': {'type': 'STRING'},
    'deadline': {'type': 'STRING'}, 'published': {'type': 'STRING'}},
    'required': ['tender', 'eng', 'types', 'summary', 'reason', 'deadline', 'published']}

def date(s):
    """Validated YYYY-MM-DD from Gemini, else None."""
    try:
        d = dt.date.fromisoformat((s or '').strip()[:10])
        return d.isoformat() if 2015 <= d.year <= 2035 else None
    except ValueError:
        return None

def judge(title, url, text, pdf=None):
    """Screen with the cheap model; anything it calls an engineering tender is re-checked by the stronger
    CONFIRM model. Returns dict (by='confirm' or 'screen' if the confirm model had no answer) or None."""
    p = PROMPT.format(scope=SCOPE, types='、'.join(TYPES), title=title, url=url, text=text[:4000] or ('（見附件 PDF）' if pdf else '（未能讀取）'))
    out = _ask(p, SCHEMA, pdf=pdf)
    if not out: return None
    out['by'] = 'screen'
    if out['tender'] and out['eng'] and CONFIRM:
        c = _ask(p, SCHEMA, CONFIRM, pdf=pdf)
        if c: out = dict(c, by='confirm')
    out['types'] = [t for t in out.get('types', []) if t in TYPES]
    return out

PICK = """以下是一間香港學校網站首頁上的連結（編號. 文字 | 網址）。
學校有時把「招標／報價／採購」公告放在不明顯的欄目，例如「學校行政」、「法團校董會」、「通告」、「下載區」、「其他」。
哪些連結最可能通往刊登這類公告的頁面？最多選 3 個，按可能性排序；全部都不可能就回覆空陣列。

{links}"""

def pick_links(links):
    """links: [(url, label)] -> indices of the most likely tender-notice pages."""
    out = _ask(PICK.format(links='\n'.join(f'{i}. {t[:40]} | {u[:150]}' for i, (u, t) in enumerate(links))),
               {'type': 'OBJECT', 'properties': {'picks': {'type': 'ARRAY', 'items': {'type': 'INTEGER'}}}, 'required': ['picks']})
    if out is None: return None
    return [i for i in out.get('picks', [])[:3] if 0 <= i < len(links)]

SITE = """用 Google 搜尋找出這間香港學校的官方網站首頁網址：
{name}（{name_en}），{kind}，{district}，地址：{address}
只回覆一個網址（不要其他文字）。要學校本身的網站，不要辦學團體總網站、教育局、學校概覽或其他目錄網站。找不到就回覆 NONE。"""

def find_site(s):
    out = _ask(SITE.format(name=s['name'], name_en=s['name_en'], kind=s['type'], district=s['district'], address=s['address']), None)
    if out is None: return None
    m = re.search(r'https?://[^\s<>"\'）)]+', out)
    return m.group(0).rstrip('.,;') if m else ''

def _ask(prompt, schema, models=None, pdf=None):
    """schema=None -> grounded with Google Search, returns plain text."""
    if not available(): return None
    cfg = {'temperature': 0, 'thinkingConfig': {'thinkingLevel': 'low'}}
    if schema: cfg.update(responseMimeType='application/json', responseSchema=schema)
    parts = [{'text': prompt}]
    if pdf: parts.append({'inline_data': {'mime_type': 'application/pdf', 'data': base64.b64encode(pdf).decode()}})
    body = {'contents': [{'parts': parts}], 'generationConfig': cfg}
    if not schema: body['tools'] = [{'google_search': {}}]
    for attempt in range(6):
        live = [m.strip() for m in (models or MODELS) if m.strip() not in _spent]
        if not live: break
        model = live[attempt % len(live)]
        _slot(model)
        if time.time() > _end: break
        try:
            r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                              headers={'x-goog-api-key': KEY}, json=body, timeout=90)
            if r.status_code == 429:
                STATS['limited'] += 1
                if 'PerDay' in r.text:
                    if model not in _spent: print('gemini daily quota used up:', model, flush=True)
                    _spent.add(model); continue
                m = re.search(r'retry in ([\d.]+)s', r.text)
                with _lock: _next[model] = max(_next.get(model, 0), time.time() + (float(m.group(1)) if m else 30))
                continue
            if r.status_code in (500, 503):
                time.sleep(5 * 2 ** (attempt // 2)); continue
            r.raise_for_status()
            text = ''.join(p.get('text', '') for p in r.json()['candidates'][0]['content']['parts'])
            out = json.loads(text) if schema else text.strip()
            STATS['ok'] += 1
            return out
        except Exception as e:
            print('gemini error', type(e).__name__, str(e)[:120], flush=True)
            time.sleep(3)
    STATS['failed'] += 1
    return None
