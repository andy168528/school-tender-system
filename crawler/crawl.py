import json, re, sys, time, os, threading, concurrent.futures as cf
from urllib.parse import urljoin, urlparse, unquote
import requests, urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings()

STRONG = re.compile(r'招標|招标|報價|报价|標書|投標|承投|採購|tender|quotation|procurement|bidding', re.I)
CONTENT = re.compile(r'招標|招标|報價|报价|標書|投標|承投|tender|quotation', re.I)
STRONG_URL = re.compile(r'tender|quotation|procure|zhaobiao|招標|報價|標書', re.I)
SECTION = re.compile(r'招標|報價|標書|投標|採購|tender|quotation|procurement', re.I)
NAV = [(re.compile(p, re.I), w) for p, w in [
    (r'最新消息|學校消息|校園消息|news', 10), (r'通告|公告|notice|announcement|circular', 9),
    (r'學校資料|學校概覽|關於|about|學校簡介|學校資訊|information|資訊', 7), (r'行政|校務|管理|administration|management|法團|校董', 7),
    (r'下載|download|文件|documents?', 6), (r'其他|others?|更多|more|雜項', 4), (r'家長|parents?', 3),
    (r'校園動態|動態|活動消息|events?', 3), (r'聯絡|contact', 2)]]
ENG = re.compile(r'工程|改裝|重組|閉路電視|CCTV|佈線|圍欄|維修|維護|保養|修葺|修繕|修理|裝修|翻新|改善|改建|加建|拆卸|更換|安裝|冷氣|空調|電力|電器|電氣|機電|水電|水喉|渠務|排水|去水|消防|樓宇|屋宇|驗樓|檢查|檢驗|測試|滲水|漏水|防水|天台|外牆|油漆|髹|粉飾|地台|地板|天花|窗戶|鋁窗|門閘|閘門|升降機|電梯|照明|燈具|供水|食水|沖廁|潔具|廁所|洗手間|校舍|圍網|棚架|石屎|混凝土|結構|白蟻|works?\b|maintenance|repair|renovat|refurbish|alteration|addition|A\s*&\s*A|E\s*&\s*M|electrical|plumbing|drain|seepage|leak|waterproof|inspection|air[- ]?condition|fire service|lift|painting|lighting|toilet|roof|fa[cç]ade|concrete|builder|upgrad|install|replace', re.I)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept-Language': 'zh-HK,zh;q=0.9,en;q=0.8'}
SKIP_EXT = re.compile(r'\.(jpg|jpeg|png|gif|bmp|svg|mp4|mp3|wmv|avi|mov|zip|rar|exe|swf|ico|css|js)(\?|$)', re.I)
DOC_EXT = re.compile(r'\.(pdf|docx?|xlsx?|pptx?)(\?|$)', re.I)
MAX_PAGES = 18
SITE_BUDGET = 200

def decode(r):
    c = r.content
    cs = None
    m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', c[:4000], re.I)
    if m: cs = m.group(1).decode('ascii', 'ignore').lower()
    elif r.encoding and 'charset' in r.headers.get('content-type', '').lower(): cs = r.encoding.lower()
    if cs in ('big5', 'big-5', 'x-x-big5'): cs = 'big5hkscs'
    if cs in ('gb2312', 'gbk'): cs = 'gb18030'
    for e in ([cs] if cs else []) + ['utf-8', 'big5hkscs', 'gb18030']:
        try: return c.decode(e)
        except Exception: pass
    return c.decode('utf-8', 'ignore')

_tl = threading.local()
def sess():
    if not hasattr(_tl, 's'):
        s = requests.Session(); s.headers.update(UA); s.verify = False; _tl.s = s
    return _tl.s

def req_fetch(url):
    r = sess().get(url, timeout=(8, 15), allow_redirects=True, stream=True)
    ct = r.headers.get('content-type', '').lower()
    if 'html' not in ct and 'xml' not in ct and ct and 'text' not in ct:
        r.close(); return r.url, None, r.status_code
    r._content = r.raw.read(1_500_000, decode_content=True)
    return r.url, decode(r), r.status_code

def norm(u): return u.split('#')[0]
def key(u): return unquote(u).split('://',1)[-1].removeprefix('www.').rstrip('/')
def host(u): return urlparse(u).netloc.lower().removeprefix('www.')

def parse(base, html):
    soup = BeautifulSoup(html, 'lxml')
    links = []
    for a in soup.find_all(['a', 'span', 'div', 'li', 'button']) if False else []: pass
    for el in soup.find_all(['a', 'span', 'button']):
        if el.name == 'a' and (el.get('href') or '').strip() and not (el.get('href') or '').strip().startswith(('javascript', '#')): continue
        lab = ' '.join(el.get_text(' ', strip=True).split())
        if len(lab) > 40 or not is_section(lab): continue
        li = el.find_parent('li')
        if not li: continue
        kids = []
        for k in li.find_all('a'):
            h = (k.get('href') or '').strip()
            if k is el or not h or h.startswith(('javascript', '#', 'mailto:')): continue
            kids.append((norm(urljoin(base, h)), ' '.join(k.get_text(' ', strip=True).split())))
        if kids: links.append(('MENU::' + lab, lab, json.dumps(kids, ensure_ascii=False)))
    for a in soup.find_all(['a', 'area']):
        href = (a.get('href') or '').strip()
        oc = a.get('onclick') or ''
        if (not href or href.startswith('javascript')) and oc:
            m = re.search(r"['\"]([^'\"]+\.(?:php|html?|aspx?|jsp|pdf)[^'\"]*)['\"]", oc)
            if m: href = m.group(1)
        if not href or href.startswith(('mailto:', 'tel:', 'javascript', '#')): continue
        t = ' '.join(a.get_text(' ', strip=True).split())
        extra = ' '.join(filter(None, [a.get('title'), *(i.get('alt') for i in a.find_all('img'))]))
        links.append((norm(urljoin(base, href)), t, extra))
    frames = [norm(urljoin(base, f.get('src'))) for f in soup.find_all(['frame', 'iframe']) if f.get('src') and not f.get('src').startswith(('javascript', 'about'))]
    m = soup.find('meta', attrs={'http-equiv': re.compile('refresh', re.I)})
    if m and m.get('content'):
        mm = re.search(r'url\s*=\s*["\']?([^"\';]+)', m['content'], re.I)
        if mm: frames.append(norm(urljoin(base, mm.group(1).strip())))
    for mm in re.finditer(r'(?:window\.|document\.|top\.)?location(?:\.href)?\s*=\s*["\']([^"\']+)["\']', html[:20000]):
        frames.append(norm(urljoin(base, mm.group(1))))
    for s in soup(['script', 'style', 'noscript']): s.decompose()
    text = ' '.join(soup.get_text(' ', strip=True).split())
    title = (soup.title.get_text(strip=True) if soup.title else '')
    return links, frames, text, title

GENERIC = re.compile(r'招標|招标|報價|报价|投標|標書|承投|採購|事宜|公告|通告|資訊|資料|項目|消息|邀請|學校|本校|服務|書面|通知|專區|及|與|和|tendering|tenders?|quotations?|procurement|notices?|invitations?|written|and|for|school|information|purchasing|[\s/&()（）、|\-–:：「」\[\]【】»>]+', re.I)
def is_section(lab):
    return bool(SECTION.search(lab)) and not re.search(r'\d', lab) and len(lab) <= 40 and len(GENERIC.sub('', lab)) <= 2

def nav_score(t, u):
    s = 0
    lab = t + ' ' + unquote(u)
    for rx, w in NAV:
        if rx.search(lab): s = max(s, w)
    return s

def crawl_site(url, fetch=req_fetch, max_pages=MAX_PAGES):
    t0 = time.time()
    res = {'site': url, 'status': None, 'final_url': None, 'tender_pages': [], 'items': [], 'content_hits': [],
           'pages': 0, 'thin': False, 'error': None, 'wp': False}
    starts = [url]
    p = urlparse(url)
    alt = ('https' if p.scheme == 'http' else 'http') + url[len(p.scheme):]
    starts.append(alt)
    home = None
    for u in starts:
        try:
            fu, html, code = fetch(u)
            if html is not None and code < 400:
                home = (fu, html); break
            res['error'] = f'HTTP {code}'
        except Exception as e:
            res['error'] = type(e).__name__ + ': ' + str(e)[:120]
    if not home:
        res['status'] = 'unreachable'; return res
    res['status'] = 'ok'; res['error'] = None; res['final_url'] = home[0]
    domains = {host(url), host(home[0])}
    seen = set(); queue = [(0, 100, home[0], home[1], 'homepage')]
    seen.add(norm(url)); seen.add(norm(home[0]))
    tender_seen = set(); item_seen = set()
    home_text_len = None
    visited = set()
    while queue and res['pages'] < max_pages and time.time() - t0 < SITE_BUDGET:
        queue.sort(key=lambda x: (-x[1], x[0]))
        depth, score, u, html, via = queue.pop(0)
        if res.get('section_done') and score < 99: break
        if key(u) in visited: continue
        visited.add(key(u))
        if html is None:
            try:
                fu, html, code = fetch(u)
                if html is None or code >= 400: continue
                domains.add(host(fu))
            except Exception: continue
        res['pages'] += 1
        if score == 99: res['section_done'] = True
        links, frames, text, title = parse(u, html)
        if home_text_len is None:
            home_text_len = len(text); res['wp'] = 'wp-content' in html
            res['thin'] = len(text) < 300 and len(links) < 15 and not frames
        if via != 'wp-search' and is_section(re.split(r'\s[|\-–]\s', title)[0].strip()):
            if key(u) not in tender_seen:
                tender_seen.add(key(u)); res['tender_pages'].append({'url': u, 'text': title[:80], 'from': via, 'kind': 'title', 'depth': depth})
        for m in (CONTENT.finditer(text) if via != 'wp-search' else []):
            if len(res['content_hits']) < 6:
                res['content_hits'].append({'page': u, 'snippet': text[max(0, m.start()-40): m.end()+60]})
            break
        for f in frames:
            if f not in seen and host(f) in domains | {host(f)} and not SKIP_EXT.search(f):
                seen.add(f); queue.append((depth, 95, f, None, u))
                domains.add(host(f))
        for lu, t, extra in links:
            if lu.startswith('MENU::'):
                res['section_done'] = True
                if '#menu' not in tender_seen:
                    tender_seen.add('#menu')
                    res['tender_pages'].append({'url': u, 'text': t + '（下拉選單）', 'from': u, 'kind': 'menu', 'depth': depth})
                for ku, kt in json.loads(extra):
                    ik = (key(ku), kt)
                    if ik in item_seen or len(res['items']) >= 80: continue
                    item_seen.add(ik)
                    res['items'].append({'text': kt, 'url': ku, 'page': u, 'doc': bool(DOC_EXT.search(ku)), 'eng': bool(ENG.search(kt + ' ' + unquote(ku))), 'menu': t})
                continue
            lab = (t or extra)[:200]
            strong = STRONG.search(t) or STRONG.search(extra) or STRONG_URL.search(unquote(lu))
            if strong:
                is_doc = bool(DOC_EXT.search(lu))
                short = is_section(lab)
                ik = (key(lu), lab)
                if short and not is_doc:
                    if key(lu) not in tender_seen:
                        tender_seen.add(key(lu)); res['tender_pages'].append({'url': lu, 'text': lab, 'from': u, 'kind': 'section', 'depth': depth})
                    if lu not in seen and host(lu) in domains:
                        seen.add(lu); queue.append((depth + 1, 99, lu, None, u))
                elif not (STRONG.search(lab) or is_doc): continue
                elif ik not in item_seen and len(res['items']) < 80:
                    item_seen.add(ik)
                    res['items'].append({'text': lab, 'url': lu, 'page': u, 'doc': is_doc, 'eng': bool(ENG.search(lab + ' ' + unquote(lu)))})
                continue
            if depth >= 2 or SKIP_EXT.search(lu) or DOC_EXT.search(lu) or lu in seen: continue
            if host(lu) not in domains: continue
            s = nav_score(t + ' ' + extra, lu)
            if s and depth < 2:
                seen.add(lu); queue.append((depth + 1, s - depth * 5, lu, None, u))
        if res['wp'] and depth == 0:
            for q in ('招標', '報價', 'tender'):
                su = home[0].rstrip('/') + '/?s=' + q
                if su not in seen: seen.add(su); queue.append((1, 98, su, None, 'wp-search'))
    return res

def main():
    schools = json.load(open('schools.json'))
    sites = sorted({x['WEBSITE'].strip() for x in schools if x['WEBSITE'] != 'N.A.'})
    if os.environ.get('SITES'): sites = [l.strip() for l in open(os.environ['SITES']) if l.strip()]
    out = sys.argv[1] if len(sys.argv) > 1 else 'results.jsonl'
    done = set()
    if os.path.exists(out):
        for l in open(out): done.add(json.loads(l)['site'])
    todo = [s for s in sites if s not in done]
    if len(sys.argv) > 2: todo = todo[:int(sys.argv[2])]
    print('sites', len(sites), 'todo', len(todo), flush=True)
    lock = threading.Lock(); n = 0
    with open(out, 'a') as f, cf.ThreadPoolExecutor(40) as ex:
        futs = {ex.submit(crawl_site, s): s for s in todo}
        for fu in cf.as_completed(futs):
            try: r = fu.result()
            except Exception as e: r = {'site': futs[fu], 'status': 'crash', 'error': repr(e)[:200], 'tender_pages': [], 'items': [], 'content_hits': [], 'pages': 0}
            with lock:
                f.write(json.dumps(r, ensure_ascii=False) + '\n'); f.flush(); n += 1
                if n % 50 == 0: print(n, time.strftime('%X'), flush=True)

if __name__ == '__main__':
    main()
