import re, datetime as dt

ENG_STRONG = re.compile(r'工程|裝修|翻新|改善|改建|加建|拆卸|改裝|冷氣|空調|電力|電氣|機電|水電|水喉|渠務|排水|消防|樓宇|屋宇|驗樓|滲水|漏水|防水|天台|外牆|油漆|髹|粉飾|地台|地板|天花|窗戶|鋁窗|門閘|閘門|升降機|電梯|照明|燈具|供水|食水|沖廁|潔具|廁所|洗手間|校舍|圍網|圍欄|棚架|石屎|混凝土|結構|白蟻|太陽能|works?\b|renovat|refurbish|alteration|addition|A\s*&\s*A|E\s*&\s*M|electrical|plumbing|drain|seepage|leak|waterproof|air[- ]?condition|ventilation|fire service|lifts?(?![a-z])|painting|lighting|toilet|roof|fa[cç]ade|concrete|builder|solar|building', re.I)
ENG_WEAK = re.compile(r'維修|維護|保養|修葺|修繕|修理|更換|安裝|檢查|檢驗|測試|閉路電視|CCTV|佈線|maintenance|repair|upgrad|install|replace|inspection|testing', re.I)
ENG_NEG = re.compile(r'網頁|網站|電腦|軟件|伺服器|網絡|影印|打印|印表|多媒體|平板|校車|校巴|午膳|小食|校服|書簿|課本|教科書|導師|課程|IT\b|software|website|web\b|network|server|computer|copier|photocop|printer|multimedia|tablet|ipad|textbook|tutor|lunch|uniform', re.I)

RESULT = re.compile(r'中標公司|中標者|中標商|中標結果|招標結果|報價結果|批出合約|awarded to|successful (?:tenderer|bidder)', re.I)
BOILER = re.compile(r'維護國家安全|國家安全|防止賄賂條例|防止串通行為|利益衝突')

def is_eng(text):
    text = BOILER.sub(' ', text)
    if ENG_STRONG.search(text) and not re.search(r'網頁|網站|website|software|軟件', text, re.I): return True
    return bool(ENG_WEAK.search(text)) and not ENG_NEG.search(text)

ENG_TYPES = [
    ('樓宇維修保養', r'樓宇維修|維修保養|大型維修|修葺|修繕|維修工程|保養工程|builder|building maintenance|repair works?|白蟻|油漆|髹|粉飾|painting|地台|地板|天花|窗戶|鋁窗|門閘|閘門|圍網|圍欄|棚架|石屎|混凝土|結構|外牆|fa[cç]ade|concrete|roof|天台|有蓋操場|校舍'),
    ('機電工程 (E&M)', r'機電|E\s*&\s*M|冷氣|空調|通風|air[- ]?condition|ventilation|升降機|電梯|lifts?(?![a-z])|消防|fire service|電力|電氣|電器|electrical|照明|燈具|lighting|太陽能|solar|閉路電視|CCTV|佈線|發電機|水泵'),
    ('水電維修', r'水電|水喉|供水|食水|沖廁|潔具|渠|排水|去水|plumbing|drain|toilet|廁所|洗手間|熱水爐'),
    ('小型工程 (Minor Works)', r'小型工程|minor works?'),
    ('改建加建 / 裝修 (A&A)', r'改建|加建|改裝|裝修|翻新|改善工程|拆卸|拆裝|A\s*&\s*A|alteration|addition|renovat|refurbish|fitting[- ]?out|conversion'),
    ('樓宇檢查 / 測試', r'驗樓|樓宇檢查|檢查|檢驗|測試|inspection|testing|survey|勘察'),
    ('滲水 / 防水', r'滲水|漏水|防水|seepage|leak|waterproof'),
]
ENG_TYPES_RX = [(n, re.compile(p, re.I)) for n, p in ENG_TYPES]
OTHER_ENG = '其他工程'
NON_ENG = '非工程（服務／物品）'

def eng_types(text):
    text = BOILER.sub(' ', text)
    if not is_eng(text): return []
    t = [n for n, rx in ENG_TYPES_RX if rx.search(text)]
    return t or [OTHER_ENG]

MON = {m: i + 1 for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}
DATE_RX = [
    (re.compile(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日'), 'ymd'),
    (re.compile(r'(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)'), 'ymd'),
    (re.compile(r'(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})(?!\d)'), 'dmy'),
    (re.compile(r'(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+(20\d{2})', re.I), 'dMy'),
    (re.compile(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})', re.I), 'Mdy'),
]
COMPACT = re.compile(r'(?<!\d)(20[12]\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)')

def _mk(y, m, d):
    try:
        x = dt.date(int(y), int(m), int(d))
        return x if 2015 <= x.year <= 2035 else None
    except Exception: return None

def find_dates(text):
    out = []
    for rx, kind in DATE_RX:
        for m in rx.finditer(text):
            g = m.groups()
            if kind == 'ymd': d = _mk(g[0], g[1], g[2])
            elif kind == 'dmy': d = _mk(g[2], g[1], g[0])
            elif kind == 'dMy': d = _mk(g[2], MON[g[1][:3].lower()], g[0])
            else: d = _mk(g[2], MON[g[0][:3].lower()], g[1])
            if d: out.append((m.start(), d))
    out.sort()
    return out

DEADLINE_KW = re.compile(r'截標|截止|截收|收標|遞交|交回|送達|提交|投放|closing|deadline|due date|on or before|not later than|no later than|submi', re.I)
STRONG_DL = re.compile(r'截標|截止|截收|收標|closing|deadline', re.I)

def find_deadline(text):
    if not text: return None
    best = None
    for rx in (STRONG_DL, DEADLINE_KW):
        for m in rx.finditer(text):
            ds = find_dates(text[m.start(): m.end() + 160])
            if ds:
                return ds[0][1]
        if best: break
    return best

def find_published(text, url=''):
    ds = find_dates(text)
    if ds: return ds[0][1]
    m = COMPACT.search(url)
    if m: return _mk(*m.groups())
    return None

SCHOOL_TYPE = {
    '幼稚園': '幼稚園', '幼稚園暨幼兒中心': '幼稚園暨幼兒中心', '資助特殊學校': '特殊學校',
}
def school_type(cat_zh, level):
    if cat_zh in SCHOOL_TYPE: return SCHOOL_TYPE[cat_zh]
    if '國際學校' in cat_zh or '英基' in cat_zh: return '國際學校' + ('（中學）' if '中學' in cat_zh else '（小學）')
    if level == 'SECONDARY' or '中學' in cat_zh: return '中學'
    if level == 'PRIMARY' or '小學' in cat_zh: return '小學'
    return cat_zh
