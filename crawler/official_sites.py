"""Read EDB's own school profile sites — 幼稚園概覽 (kindergartenprofile.com) and 中學／小學概覽 (chsc.hk) — for
each school's current website and 辦學團體 (sponsoring body). Saves crawler/profiles.json.
  * website: replaces an outdated EDB-list URL when it differs, loads, and the school isn't already monitored
    (written to found_sites.json with src = profile name; build_schools() uses it instead of the EDB URL).
  * sponsor: from the profile; schools without one (kindergartens etc.) get it inferred from a name prefix that
    profiled schools of a single sponsor share (e.g. 保良局…). build_schools() adds both to schools.json.
`python official_sites.py cached` reuses profiles.json instead of re-downloading."""
import concurrent.futures as cf, json, os, re, sys, time
import crawl, monitor

KGP = 'https://kgp2026.kindergartenprofile.com/school/?schid={}'
CHSC = {'中學概覽': 'https://www.chsc.hk/ssp2025/', '小學概覽': 'https://www.chsc.hk/psp2026/'}
URL = r'(https?://[^\s"<>&|]+)'
PROFILES = os.path.join(monitor.HERE, 'profiles.json')

def get(u, tries=3):
    for a in range(tries):
        try:
            fu, html, code = crawl.req_fetch(u)
            if html and code < 400: return html
        except Exception:
            pass
        time.sleep(2 + 3 * a)
    return ''

def text(html):
    return ' '.join(re.sub(r'<[^>]+>', ' ', re.sub(r'(?s)<(script|style).*?</\1>', '', html)).replace('&nbsp;', ' ').split())

def sponsor(x):
    x = re.split(r'\s+(?:法團校董會|校監|宗教|創校年份)\s*:', x or '')[0].strip()
    return re.sub(r'(?<=[\u4e00-\u9fff（）])\s+(?=[\u4e00-\u9fff（）])', '', x)

def clean(u): return u.rstrip('/.') if u else None

def kg_site(sid):
    m = re.search(r'學校網址\s*(?:<[^>]+>\s*)*' + URL, get(KGP.format(sid)))
    return clean(m and m.group(1))

def chsc(base):
    ids = set()
    for d in range(1, 19):
        ids |= set(re.findall(r'sch_detail\.php\?[^"\']*sch_id=(\d+)', get(f'{base}sch_list.php?li_id=2&district_id={d}&lang_id=2&frmMode=pagebreak')))
    def one(i):
        t = text(get(f'{base}sch_detail.php?li_id=2&lang_id=2&sch_id={i}'))
        g = lambda p: (m.group(1).strip() if (m := re.search(p, t)) else '')
        return {'phone': re.sub(r'\D', '', g(r'電話:\s*([\d ]{8,})'))[:8], 'url': clean(g(r'網址:\s*' + URL)),
                'sponsor': sponsor(g(r'辦學團體\s*:\s*(.+?)\s+(?:宗教|創校年份)\s*:'))}
    with cf.ThreadPoolExecutor(4) as ex: return [r for r in ex.map(one, sorted(ids)) if r['phone']]

def collect(schools):
    kg = sorted({s['id'][:10] for s in schools if '幼稚園' in s['type']})
    print('kindergarten profiles', len(kg), flush=True)
    with cf.ThreadPoolExecutor(6) as ex: kgu = dict(zip(kg, ex.map(kg_site, kg)))
    print('  with website', sum(map(bool, kgu.values())), flush=True)
    out = {'kg': kgu}
    for src, base in CHSC.items():
        out[src] = chsc(base)
        print(src, len(out[src]), flush=True)
    json.dump(out, open(PROFILES, 'w'), ensure_ascii=False)
    return out

def resolve(schools, prof):
    """-> {sid: {'url', 'src', 'sponsor', 'sponsor_src'}}"""
    res = {}
    for s in schools:
        r = res.setdefault(s['id'], {})
        if prof['kg'].get(s['id'][:10]): r.update(url=prof['kg'][s['id'][:10]], src='幼稚園概覽')
    for src in CHSC:
        level = '中學' if src == '中學概覽' else '小學'
        by_phone = {p['phone']: p for p in prof[src]}
        for s in schools:
            p = by_phone.get(s['phone'].replace(' ', '')[:8])
            if level not in s['type'] or not p: continue
            r = res[s['id']]
            if p['url'] and 'url' not in r: r.update(url=p['url'], src=src)
            if sponsor(p['sponsor']): r.update(sponsor=sponsor(p['sponsor']), sponsor_src=src)
    # name-prefix → sponsor, when ≥3 profiled schools share the prefix and all have the same sponsor
    known = [(s['name'], res[s['id']]['sponsor']) for s in schools if res[s['id']].get('sponsor')]
    pre = {}
    for L in range(2, 7):
        cnt = {}
        for n, sp in known:
            if len(n) > L: cnt.setdefault(n[:L], {}).setdefault(sp, 0); cnt[n[:L]][sp] += 1
        for k, c in cnt.items():
            sp, n = max(c.items(), key=lambda x: x[1])
            if n >= 3 and n == sum(c.values()): pre[k] = sp
    for s in schools:
        r = res[s['id']]
        if r.get('sponsor'): continue
        for L in range(6, 1, -1):
            if s['name'][:L] in pre: r.update(sponsor=pre[s['name'][:L]], sponsor_src='按校名推斷'); break
    return res

def host(u): return crawl.key(u).split('/')[0]

def same_site_ok(s, u, sites):
    """Profile only points to another page of a site we can already read: keep crawling from the current URL."""
    return bool(s['website']) and host(u) == host(s['website']) and sites.get(s['website'], {}).get('reason') not in ('網站無法連線', '尚未掃描', None)

def new_site_failed(s, u, sites):
    """Profile URL was tried before and couldn't be reached, while the EDB URL could: keep the EDB URL."""
    old = sites.get(s.get('website_edb', s['website']), {}).get('reason')
    return sites.get(u, {}).get('reason') == '網站無法連線' and old not in ('網站無法連線', '尚未掃描', None)

def main():
    schools = monitor.build_schools(monitor.load_edb())
    prof = json.load(open(PROFILES)) if 'cached' in sys.argv and os.path.exists(PROFILES) else collect(schools)
    res = resolve(schools, prof)
    monitor.save_sponsors({sid: {k: r[k] for k in ('sponsor', 'sponsor_src')} for sid, r in res.items() if r.get('sponsor')})
    sites = {s['site']: s for s in monitor.load('sites.json', [])}
    found = monitor.load('found_sites.json', {})
    cand = [(s['id'], res[s['id']]['url'], res[s['id']]['src']) for s in schools
            if res[s['id']].get('url') and not sites.get(s['website'], {}).get('monitored')
            and crawl.key(res[s['id']]['url']) != crawl.key(s['website'] or 'x') and not same_site_ok(s, res[s['id']]['url'], sites)
            and not new_site_failed(s, res[s['id']]['url'], sites)]
    print('official URL differs from current (not monitored)', len(cand), flush=True)
    n = 0
    with cf.ThreadPoolExecutor(8) as ex:
        for (sid, u, src), good in zip(cand, ex.map(lambda c: bool(get(c[1], 2)), cand)):
            if good: found[sid] = {'url': u, 'at': monitor.TODAY, 'src': src}; n += 1
            print('OK ' if good else '-- ', sid, u, src, flush=True)
    for s in schools:
        f = found.get(s['id'], {})
        if f.get('src') in (*CHSC, '幼稚園概覽') and new_site_failed(s, f['url'], sites): found.pop(s['id']); print('revert', s['id'], f['url'])
    monitor.save('found_sites.json', found)
    print('updated', n, 'schools to official websites; sponsors', sum(bool(r.get('sponsor')) for r in res.values()))

if __name__ == '__main__':
    main()
