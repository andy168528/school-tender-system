"""Ask Gemini (Google Search) for the website of schools whose EDB entry has none or whose site can't be reached.
A URL is kept only if it loads and the page mentions the school's name. Results go to found_sites.json,
which build_schools() uses in place of the EDB website."""
import concurrent.futures as cf, re, sys
import crawl, ai, monitor

def names(s):
    zh = re.sub(r'[（(].*?[)）]', '', s['name'])
    return [zh, zh.replace('學校', ''), s['name_en'].split('(')[0].strip().lower()]

def verify(s, url):
    try:
        fu, html, code = crawl.req_fetch(url)
    except Exception:
        return None
    if not html or code >= 400: return None
    text = html.lower()
    return fu if any(n and len(n) >= 4 and n.lower() in text for n in names(s)) else None

def main():
    schools = monitor.build_schools(monitor.load_edb())
    sites = {s['site']: s for s in monitor.load('sites.json', [])}
    found = monitor.load('found_sites.json', {})
    todo = [s for s in schools if s['id'] not in found and (not s.get('website_edb', s['website'])
            or sites.get(s['website'], {}).get('reason') == '網站無法連線')]
    groups = {}
    for s in todo: groups.setdefault((s['name'], s['address']), []).append(s)
    print('schools to look up', len(todo), 'unique', len(groups), flush=True)
    def work(s):
        u = ai.find_site(s) if ai.available() else None
        if u is None: return s, None, None
        if not u or crawl.key(u) == crawl.key(s['website'] or 'x'): return s, u, None
        return s, u, verify(s, u)
    with cf.ThreadPoolExecutor(8) as ex:
        for s, u, ok in ex.map(work, [g[0] for g in groups.values()]):
            if u is None: continue
            print('OK ' if ok else '-- ', s['name'], '|', s['website'] or '(無)', '->', u, flush=True)
            for x in groups[(s['name'], s['address'])]: found[x['id']] = {'url': ok, 'at': monitor.TODAY}
    monitor.save('found_sites.json', found)
    print('found', sum(1 for s in todo if found.get(s['id'], {}).get('url')), 'checked', sum(1 for s in todo if s['id'] in found), 'of', len(todo), 'gemini', ai.STATS)

if __name__ == '__main__':
    main()
