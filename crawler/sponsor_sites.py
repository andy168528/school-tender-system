"""Find each school sponsoring body's (辦學團體) official site and its tender/quotation page.
Gemini (Google Search) proposes URLs; a URL is kept only if a real browser loads it and the crawler sees a
tender section or tender notices there. Result: public/data/sponsor_sites.json, crawled daily by monitor.py."""
import concurrent.futures as cf, json, re, sys
from urllib.parse import urlparse, unquote
import crawl, ai, monitor

MIN_SCHOOLS = 3
SKIP = {'政府', '教育局', '香港特區政府'}  # government schools: works are handled by ArchSD, not tendered by the school
ASK = """用 Google 搜尋，找出香港辦學團體「{name}」（辦學的學校包括：{eg}）的官方網站，以及該網站上刊登「招標／報價／tender／quotation」公告的頁面。
只回覆兩行：
HOME: <官方網站首頁網址，找不到寫 NONE>
TENDER: <招標或報價公告頁網址，找不到寫 NONE>
不要學校本身的網站、政府網站、新聞或招聘網站。"""
URL = r'(https?://[^\s<>"\'）)\]]+)'

def counts(schools):
    c = {}
    for s in schools:
        if s.get('sponsor') and s['sponsor'] not in SKIP: c.setdefault(s['sponsor'], []).append(s)
    return {k: v for k, v in c.items() if len(v) >= MIN_SCHOOLS}

def ask(name, schools):
    out = ai._ask(ASK.format(name=name, eg='、'.join(s['name'] for s in schools[:3])), None)
    if out is None: return None
    g = lambda k: (m.group(1).rstrip('.,;') if (m := re.search(k + r':\s*' + URL, out)) else '')
    return {'home': g('HOME'), 'tender': g('TENDER')}

TENDER_URL = re.compile(r'tender|quotation|招標|報價|报价', re.I)

def host(u):
    h = urlparse(u).netloc.lower()
    return h[4:] if h.startswith('www.') else h

def probe(urls, home=''):
    """Browser-crawl candidate URLs; -> (url, result) of the best one that is on the sponsor's own site and is
    really a tender page (a tender section was found, or the page's address says tender/招標)."""
    import pw
    if pw._pw is None: pw.init()
    best = None
    for u in urls:
        if home and not (host(u) + '.').endswith('.' + host(home) + '.') and not (host(home) + '.').endswith('.' + host(u) + '.') and host(u) != host(home):
            print('   skip other site', u, flush=True); continue
        r = pw.work(u)
        ok, reason, mu, ml, conf = monitor.site_verdict(r)
        url = mu if conf == '高' else u
        real = bool(r.get('tender_pages')) or conf == '高' or TENDER_URL.search(unquote(url))
        print('   probe', u, r['status'], reason or conf, len(r['items']), 'tender page' if real else 'not a tender page', flush=True)
        if ok and real and (best is None or len(r['items']) > len(best[1]['items'])): best = (url, r)
    return best

def check(job):
    k, cands, home = job
    return k, (probe(cands, home) if cands else None)

def main():
    schools = monitor.build_schools(monitor.load_edb())
    groups = counts(schools)
    out = monitor.load('sponsor_sites.json', {})
    redo = 'redo' in sys.argv
    todo = [k for k in sorted(groups, key=lambda k: -len(groups[k])) if (redo or k not in out) and 'probe' not in sys.argv]
    print('sponsors', len(groups), 'todo', len(todo), flush=True)
    with cf.ThreadPoolExecutor(6) as ex:
        asked = dict(zip(todo, ex.map(lambda k: ask(k, groups[k]), todo)))
    print("asked", ai.STATS, flush=True)
    for k, a in asked.items():
        if a is None: continue  # Gemini unavailable: try again next time
        print(k, len(groups[k]), a, flush=True)
        prev = out.get(k, {})
        out[k] = {'schools': len(groups[k]), 'home': a['home'] or prev.get('home', ''), 'hint': a['tender'] or prev.get('hint', ''),
                  'checked': monitor.TODAY, 'url': prev.get('url', ''), 'reason': '找不到網站'}
    monitor.save('sponsor_sites.json', out)
    jobs = [(k, [u for u in dict.fromkeys([out[k].get('hint'), out[k].get('url'), out[k].get('home')]) if u], out[k].get('home', '')) for k in out
            if k in asked or 'probe' in sys.argv]
    with cf.ProcessPoolExecutor(4) as ex:
        for k, best in ex.map(check, jobs):
            if best: out[k].update(url=best[0], reason='')
            elif out[k].get('home'): out[k]['reason'] = '未找到招標頁'
            print('=>', k, out[k]['url'] or out[k]['reason'], flush=True)
    monitor.save('sponsor_sites.json', out)
    print('with tender page', sum(bool(v['url']) for v in out.values()), 'of', len(out), 'gemini', ai.STATS)

if __name__ == '__main__':
    main()
