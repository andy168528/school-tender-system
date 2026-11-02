"""For sites where no tender page was found, ask Gemini which homepage links lead to tender notices.
Sites where those pages show tender items become monitored; the pages are kept in sites.json `ai_pages`
so the daily crawl starts from them."""
import concurrent.futures as cf
import crawl, ai, monitor

def home_links(site):
    for u in (site, site.replace('http://', 'https://', 1) if site.startswith('http://') else site.replace('https://', 'http://', 1)):
        try:
            fu, html, code = crawl.req_fetch(u)
        except Exception:
            continue
        if html is None or code >= 400: continue
        links, frames, _, _ = crawl.parse(fu, html)
        for f in frames[:2]:
            try:
                ffu, fh, fc = crawl.req_fetch(f)
                if fh and fc < 400: links += crawl.parse(ffu, fh)[0]
            except Exception:
                pass
        out, seen = [], set()
        for lu, t, extra in links:
            lab = (t or extra or '').strip()
            if lu.startswith('MENU::') or not lu.startswith('http') or not lab or crawl.SKIP_EXT.search(lu) or crawl.DOC_EXT.search(lu): continue
            if crawl.key(lu) in seen: continue
            seen.add(crawl.key(lu)); out.append((lu, lab))
        return out[:250]
    return []

def work(s):
    if not ai.available(): return s, None, None
    links = home_links(s['site'])
    if not links:
        s['ai_checked'] = monitor.TODAY; return s, None, []
    picks = ai.pick_links(links)
    if picks is None: return s, None, None
    s['ai_checked'] = monitor.TODAY
    if not picks: return s, None, []
    pages = [links[i][0] for i in picks]
    return s, monitor.safe(lambda u: crawl.crawl_site(u, extra=pages), s['site']), pages

def main():
    sites = {s['site']: s for s in monitor.load('sites.json', [])}
    todo = [s for s in sites.values() if not s.get('monitored') and s.get('reason') == '未找到招標資訊' and not s.get('ai_checked')]
    print('sites to check', len(todo), flush=True)
    found = 0
    with cf.ThreadPoolExecutor(16) as ex:
        for n, (s, r, pages) in enumerate(ex.map(work, todo), 1):
            if r and r['status'] == 'ok':
                ok, reason, mu, ml, conf = monitor.site_verdict(r)
                if ok and conf != '低':
                    s.update(monitored=True, reason='', monitor_url=mu, monitor_label=ml, confidence=conf, ai_pages=pages)
                    found += 1; print('found', s['site'], mu, ml, flush=True)
            if n % 100 == 0: print(n, '/', len(todo), 'found', found, flush=True)
    monitor.save('sites.json', sorted(sites.values(), key=lambda s: s['site']))
    print('newly monitored', found, 'checked', sum(bool(s.get('ai_checked')) for s in todo), 'of', len(todo), 'gemini', ai.STATS)

if __name__ == '__main__':
    main()
