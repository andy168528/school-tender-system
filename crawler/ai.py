"""Gemini check of each notice: is it a new tender, is it engineering, which types."""
import json, os, re, threading, time, requests
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
    return bool(KEY) and time.time() < _end and len(_spent) < len(MODELS)

def _slot(model):
    with _lock:
        now = time.time(); at = max(now, _next.get(model, 0))
        _next[model] = at + 60 / RPM
    time.sleep(at - now)
TYPES = [n for n, _ in classify.ENG_TYPES] + [classify.OTHER_ENG]

PROMPT = """你是香港學校招標公告的分類員。以下是學校網站上的一個連結（標題、檔名及文件開頭內容）。
請判斷：
1. tender：這是否一份「仍在邀請供應商投標／報價」的公告或標書文件？中標結果、中標公司名單、招聘、通告、已批出合約一覽表等都是 false。
2. eng：項目本身是否建築／維修／機電／水電／裝修／樓宇檢查／防水等工程？物品採購、IT、交流團、午膳、教學服務、清潔、保安等都是 false。不要因為文件內的標準條款（例如「維護國家安全」、「防止賄賂條例」）而判斷為工程。
3. types：如 eng 為 true，從以下選一個或多個：{types}
4. summary：用繁體中文一句話（30字內）說明項目內容。

標題：{title}
網址：{url}
文件內容：
{text}"""

SCHEMA = {'type': 'OBJECT', 'properties': {
    'tender': {'type': 'BOOLEAN'}, 'eng': {'type': 'BOOLEAN'},
    'types': {'type': 'ARRAY', 'items': {'type': 'STRING', 'enum': TYPES}},
    'summary': {'type': 'STRING'}}, 'required': ['tender', 'eng', 'types', 'summary']}

def judge(title, url, text):
    """Returns dict or None (no key / out of budget / API error)."""
    out = _ask(PROMPT.format(types='、'.join(TYPES), title=title, url=url, text=text[:4000] or '（未能讀取）'), SCHEMA)
    if out: out['types'] = [t for t in out.get('types', []) if t in TYPES]
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

def _ask(prompt, schema):
    """schema=None -> grounded with Google Search, returns plain text."""
    if not available(): return None
    cfg = {'temperature': 0, 'thinkingConfig': {'thinkingLevel': 'low'}}
    if schema: cfg.update(responseMimeType='application/json', responseSchema=schema)
    body = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': cfg}
    if not schema: body['tools'] = [{'google_search': {}}]
    for attempt in range(6):
        live = [m.strip() for m in MODELS if m.strip() not in _spent]
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
