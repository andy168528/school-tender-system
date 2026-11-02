import json, sys, os, time, multiprocessing as mp
import crawl
from crawl import crawl_site

_pw = None
def init():
    global _pw, _br, _ctx
    from playwright.sync_api import sync_playwright
    _pw = sync_playwright().start()
    _br = _pw.chromium.launch(args=['--ignore-certificate-errors'])
    _ctx = _br.new_context(ignore_https_errors=True, user_agent=crawl.UA['User-Agent'], locale='zh-HK')

def pw_fetch(url):
    if crawl.DOC_EXT.search(url): return url, None, 200
    p = _ctx.new_page()
    try:
        r = p.goto(url, wait_until='domcontentloaded', timeout=30000)
        try: p.wait_for_load_state('networkidle', timeout=6000)
        except Exception: pass
        html = p.content()
        for fr in p.frames[1:6]:
            try: html += '\n' + fr.content()
            except Exception: pass
        ct = (r.headers.get('content-type', '') if r else '')
        if ct and 'html' not in ct and 'text' not in ct: return p.url, None, r.status
        return p.url, html, (r.status if r else 200)
    finally:
        p.close()

def work(site):
    try:
        r = crawl_site(site, fetch=pw_fetch, max_pages=10)
    except Exception as e:
        r = {'site': site, 'status': 'crash', 'error': repr(e)[:200], 'tender_pages': [], 'items': [], 'content_hits': [], 'pages': 0}
    r['browser'] = True
    return r

if __name__ == '__main__':
    sites = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    out = sys.argv[2]
    done = {json.loads(l)['site'] for l in open(out)} if os.path.exists(out) else set()
    todo = [s for s in sites if s not in done]
    print('todo', len(todo), flush=True)
    n = 0
    with mp.Pool(8, initializer=init) as pool, open(out, 'a') as f:
        for r in pool.imap_unordered(work, todo):
            f.write(json.dumps(r, ensure_ascii=False) + '\n'); f.flush(); n += 1
            if n % 20 == 0: print(n, time.strftime('%X'), flush=True)
