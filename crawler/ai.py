"""Gemini check of each notice: is it a new tender, is it engineering, which types."""
import json, os, time, requests
import classify

KEY = os.environ.get('GEMINI_API_KEY', '').strip()
MODELS = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash,gemini-3.5-flash-lite').split(',')
BUDGET = 20 * 60
_end = time.time() + BUDGET
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
    if not KEY or time.time() > _end: return None
    body = {'contents': [{'parts': [{'text': PROMPT.format(types='、'.join(TYPES), title=title, url=url, text=text[:4000] or '（未能讀取）')}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': SCHEMA, 'temperature': 0,
                                 'thinkingConfig': {'thinkingLevel': 'low'}}}
    for attempt in range(4):
        model = MODELS[min(attempt // 2, len(MODELS) - 1)].strip()
        try:
            r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                              headers={'x-goog-api-key': KEY}, json=body, timeout=90)
            if r.status_code in (429, 500, 503):
                time.sleep(5 * 2 ** attempt); continue
            r.raise_for_status()
            out = json.loads(r.json()['candidates'][0]['content']['parts'][0]['text'])
            out['types'] = [t for t in out.get('types', []) if t in TYPES]
            return out
        except Exception as e:
            print('gemini error', type(e).__name__, str(e)[:120], flush=True)
            time.sleep(3)
    return None
