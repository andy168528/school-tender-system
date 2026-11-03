"""Daily monitor: crawl monitored school sites, update public/data/*.json.

Usage:
  python crawler/monitor.py bootstrap results.jsonl [more.jsonl ...]   # seed from a previous full scan
  python crawler/monitor.py daily                                       # re-check monitored sites
  python crawler/monitor.py full                                        # re-scan every site (weekly)
"""
import json, os, re, sys, time, hashlib, io, datetime as dt, concurrent.futures as cf
from urllib.parse import unquote
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crawl, classify, r2, ai

DATA = os.path.join(HERE, '..', 'public', 'data')
EDB_URL = 'https://www.edb.gov.hk/attachment/en/student-parents/sch-info/sch-search/sch-location-info/SCH_LOC_EDB.json'
HKT = ZoneInfo('Asia/Hong_Kong')
TODAY = dt.datetime.now(HKT).date().isoformat()
NOW = dt.datetime.now(HKT).isoformat(timespec='seconds')
MISS_LIMIT = 3

def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else default

def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    tmp = os.path.join(DATA, name + '.tmp')
    with open(tmp, 'w') as f: json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, os.path.join(DATA, name))

def load_edb():
    p = os.path.join(HERE, 'schools_edb.json')
    try:
        r = crawl.sess().get(EDB_URL, timeout=60)
        d = r.json()
        if isinstance(d, list) and len(d) > 2000:
            json.dump(d, open(p, 'w'), ensure_ascii=False)
            return d
    except Exception as e:
        print('EDB download failed, using cached list:', e)
    return json.load(open(p))

def build_schools(edb):
    found = load('found_sites.json', {})
    out = {}
    for x in edb:
        sid = str(x['SCHOOL NO.'])
        if sid in out: continue
        site = x['WEBSITE'].strip() if x['WEBSITE'] != 'N.A.' else ''
        out[sid] = {'id': sid, 'name': x['中文名稱'], 'name_en': x['ENGLISH NAME'],
                    'type': classify.school_type(x['中文類別'], x['SCHOOL LEVEL']), 'category': x['中文類別'],
                    'finance': x['資助種類'], 'district': x['分區'], 'address': x['中文地址'],
                    'phone': x['聯絡電話'] if x['聯絡電話'] != 'N.A.' else '', 'website': site}
        if found.get(sid, {}).get('url'):
            out[sid].update(website=found[sid]['url'], website_src='Gemini', website_edb=site)
    return sorted(out.values(), key=lambda s: s['id'])

def is_named(i):
    return bool(crawl.STRONG.search(i['text']) or crawl.STRONG_URL.search(unquote(i['url'])) or i.get('menu'))

def site_verdict(r):
    """-> (monitorable, reason, monitor_url, monitor_label, confidence)"""
    if r['status'] != 'ok':
        if re.match(r'HTTP (403|405|429|503)', r.get('error') or ''):
            return False, '網站拒絕程式讀取', '', '', ''
        return False, '網站無法連線', '', '', ''
    tps = [t for t in r['tender_pages'] if not crawl.DOC_EXT.search(t['url'])]
    if tps:
        tps.sort(key=lambda t: (0 if re.search(r'招標|tender', t['text'], re.I) else 1, t['depth'], 0 if t['kind'] == 'section' else 1, len(t['url'])))
        return True, '', tps[0]['url'], tps[0]['text'], '高'
    named = [i for i in r['items'] if is_named(i)]
    if named:
        from collections import Counter
        pg = Counter(i['page'] for i in named).most_common(1)[0][0]
        return True, '', pg, '公告所在頁', '中'
    hits = [h for h in r.get('content_hits', []) if '?s=' not in h['page'] and crawl.CONTENT.search(h['snippet'])]
    if hits:
        return True, '', hits[0]['page'], hits[0]['snippet'][:60], '低'
    return False, '未找到招標資訊', '', '', ''

def tender_id(site, i):
    return hashlib.sha1((crawl.key(site) + '|' + crawl.key(i['url']) + '|' + i['text'].strip()).encode()).hexdigest()[:14]

AI_BACKFILL = int(os.environ.get('AI_BACKFILL', 400))
EXTRA = {}
PRUNE_FAILED = []

def fetch_text(t):
    """(text, pdf) of the notice: PDF / Word / HTML text ('' if unreadable); pdf = raw bytes when the PDF
    has no text layer (scanned), so Gemini can read the page images itself."""
    text, pdf = '', None
    try:
        u = crawl.doc_url(t['url'])
        if u != t['url'] or crawl.DOC_EXT.search(t['url']):
            r = crawl.sess().get(u, timeout=(10, 60), stream=True)
            data = r.raw.read(30_000_000, decode_content=True)
            if b'%PDF-' in data[:1024]:
                from pypdf import PdfReader
                rd = PdfReader(io.BytesIO(data))
                text = ' '.join((p.extract_text() or '') for p in rd.pages[:4])
                t['pdf_text'] = bool(text.strip())
                t['doc'] = True
                if len(text.strip()) < 80 and len(data) < 7_000_000: pdf = data
            elif data[:2] == b'PK':
                import zipfile
                z = zipfile.ZipFile(io.BytesIO(data))
                if 'word/document.xml' in z.namelist():
                    text = re.sub(r'<[^>]+>', ' ', z.read('word/document.xml').decode('utf-8', 'ignore'))[:30000]
                    t['doc'] = True
        else:
            fu, html, code = crawl.req_fetch(t['url'])
            if html and code < 400:
                text = crawl.parse(fu, html)[2][:30000]
    except Exception as e:
        t['detail_error'] = type(e).__name__
    return ' '.join(text.split()), pdf

def needs_ai(t):
    a = t.get('ai')
    return t.get('detail_checked') and (not a or a.get('v') != ai.VERSION or (a.get('by') == 'screen' and a['tender'] and a['eng']))

def extract_detail(t):
    """Fetch the notice (PDF/HTML) once and pull deadline / published date."""
    text, pdf = fetch_text(t)
    if not t.get('deadline'):
        d = classify.find_deadline(text)
        if d: t['deadline'] = d.isoformat(); t['deadline_src'] = '文件內容'
    if not t.get('published') and text and t.get('doc'):
        d = classify.find_published(text[:600])
        if d and d.isoformat() <= TODAY and d.isoformat() != t.get('deadline'): t['published'] = d.isoformat(); t['published_src'] = '文件內容'
    j = ai.judge(t['title'], unquote(t['url']), text, pdf)
    if j:
        d, p = (ai.date(j.get('deadline')), ai.date(j.get('published'))) if text or pdf else (None, None)
        if d and not t.get('deadline'): t['deadline'] = d; t['deadline_src'] = 'AI 讀取文件'
        if p and p <= TODAY and p != t.get('deadline') and t.get('published_src') in (None, '網址'):
            t['published'] = p; t['published_src'] = 'AI 讀取文件'
        t['ai'] = {'tender': j['tender'], 'eng': j['eng'], 'summary': j['summary'][:80], 'reason': j.get('reason', '')[:120],
                   'by': j['by'], 'v': ai.VERSION}
        t['eng_types'] = (j['types'] or [classify.OTHER_ENG]) if j['tender'] and j['eng'] else []
        t['types_src'] = 'AI'
    elif classify.RESULT.search(text[:3000]):
        t['eng_types'] = []
    elif not t.get('eng_types') and text and t.get('doc') and not classify.ENG_NEG.search(t['title'] + ' ' + unquote(t['url'])):
        et = classify.eng_types(t['title'] + ' ' + text[:400])
        if et: t['eng_types'] = et; t['types_src'] = '文件內容'
    if not t.get('published'):
        d = classify.find_published('', unquote(t['url']))
        if d and d.isoformat() <= TODAY: t['published'] = d.isoformat(); t['published_src'] = '網址'
    t['detail_checked'] = TODAY

GENERIC_TITLE = re.compile(r'^(下載|按此下載|按此|點擊下載|附件|附件連結|連結|檔案|文件|詳情|pdf|download|click here|here|more|link)$', re.I)

def nice_title(text, url):
    text = text.strip()
    if text and not GENERIC_TITLE.match(re.sub(r'[\s:：>»\[\]()（）]', '', text)): return text
    name = unquote(url.split('?')[0].rstrip('/').rsplit('/', 1)[-1])
    return re.sub(r'\.\w{2,5}$', '', name) or text

def new_tender(site, i):
    label = i['text'] + ' ' + unquote(i['url'])
    t = {'id': tender_id(site, i), 'site': site, 'title': nice_title(i['text'], i['url']),
         'url': i['url'], 'page': i['page'], 'doc': bool(i.get('doc')), 'eng_types': classify.eng_types(label),
         'first_seen': TODAY, 'last_seen': TODAY, 'miss': 0}
    d = classify.find_deadline(i['text'])
    if d: t['deadline'] = d.isoformat(); t['deadline_src'] = '標題'
    p = classify.find_published(i['text'], i['url'])
    if p and p.isoformat() <= TODAY and p.isoformat() != t.get('deadline'): t['published'] = p.isoformat(); t['published_src'] = '標題'
    return t

def merge(sites, tenders, results, full, dropped):
    by_site = {}
    for t in tenders.values(): by_site.setdefault(t['site'], []).append(t)
    new = []
    for r in results:
        site = r['site']; s = sites.setdefault(site, {'site': site})
        ok, reason, mu, ml, conf = site_verdict(r)
        s['last_checked'] = NOW
        if r['status'] == 'ok':
            s['last_ok'] = NOW; s['fail'] = 0; s.pop('error', None)
        else:
            s['fail'] = s.get('fail', 0) + 1; s['error'] = (r.get('error') or '')[:120]
        if r.get('browser'): s['browser'] = True
        if ok:
            s.update(monitored=True, reason='', monitor_url=mu, monitor_label=ml, confidence=conf)
        elif (full or s.get('reason') == '尚未掃描') and not s.get('monitored'):
            s.update(monitored=False, reason=reason)
        elif 'monitored' not in s:
            s.update(monitored=False, reason=reason)
        if r['status'] != 'ok': continue
        seen = set()
        for i in r['items']:
            if not is_named(i) or crawl.is_section(i['text']): continue
            tid = tender_id(site, i)
            if tid in seen or tid in dropped: continue
            seen.add(tid)
            if tid in tenders:
                t = tenders[tid]; t['last_seen'] = TODAY; t['miss'] = 0
            else:
                t = new_tender(site, i); tenders[tid] = t; new.append(t)
        for t in by_site.get(site, []):
            if t['id'] not in seen and t.get('last_seen') != TODAY: t['miss'] = t.get('miss', 0) + 1
    for t in tenders.values(): t['active'] = t.get('miss', 0) < MISS_LIMIT
    return new

BROWSER_BUDGET = 20 * 60
BROWSER_STALL = crawl.SITE_BUDGET + 120

def run_crawl(site_list, browser_sites):
    results = []
    req_sites = [s for s in site_list if s not in browser_sites]
    with cf.ThreadPoolExecutor(32) as ex:
        for n, r in enumerate(ex.map(lambda s: safe(lambda u: crawl.crawl_site(u, extra=EXTRA.get(u, ())), s), req_sites), 1):
            results.append(r)
            if n % 50 == 0: print('crawled', n, '/', len(req_sites), time.strftime('%X'), flush=True)
    bs = [s for s in site_list if s in browser_sites]
    failed = [r['site'] for r in results if r['status'] != 'ok']
    retry = bs + failed
    if retry:
        try:
            import multiprocessing as mp, pw
            got, end = {}, time.time() + BROWSER_BUDGET
            pool = mp.get_context('spawn').Pool(6, initializer=pw.init)
            try:
                it = pool.imap_unordered(pw.work, retry)
                while True:
                    left = end - time.time()
                    if left <= 0: raise mp.TimeoutError
                    r = it.next(timeout=min(BROWSER_STALL, left))
                    got[r['site']] = r
            except StopIteration:
                pass
            except mp.TimeoutError:
                print('browser pass stopped early', len(got), '/', len(retry), flush=True)
            finally:
                pool.terminate()
            results = [got.get(r['site'], r) if r['status'] != 'ok' and got.get(r['site'], {}).get('status') == 'ok' else r for r in results]
            results += [got[s] for s in bs if s in got]
        except Exception as e:
            print('browser pass skipped:', e)
    return results

def prune(tenders, dropped):
    """Keep only engineering tenders. Ones Gemini rejected or whose file is dead are deleted and remembered in
    dropped.json. Rule-only rejects stay (hidden in UI) until Gemini judges them, unless already off the site."""
    gone = []
    for tid, t in list(tenders.items()):
        a = t.get('ai')
        bad = bool(a and not (a['tender'] and a['eng'])) or t.get('backup_state') == 'dead'
        if bad or (not a and not t.get('eng_types') and not t.get('active', True)):
            gone.append(tenders.pop(tid))
            if bad: dropped[tid] = TODAY
    failed = [t['backup'] for t in gone if t.get('backup') and not (r2.enabled() and r2.delete(t['backup']))]
    print('pruned', len(gone), 'remembered', sum(t['id'] in dropped for t in gone), 'R2 delete failed', len(failed), flush=True)
    PRUNE_FAILED.extend(failed)
    return gone

def safe(fn, s):
    try: return fn(s)
    except Exception as e:
        return {'site': s, 'status': 'crash', 'error': repr(e)[:200], 'tender_pages': [], 'items': [], 'content_hits': [], 'pages': 0}

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'daily'
    t0 = time.time()
    edb = load_edb()
    schools = build_schools(edb)
    sites = {s['site']: s for s in load('sites.json', [])}
    tenders = {t['id']: t for t in load('tenders.json', [])}
    dropped = load('dropped.json', {})
    EXTRA.update({s['site']: s['ai_pages'] for s in sites.values() if s.get('ai_pages')})
    all_sites = sorted({s['website'] for s in schools if s['website']})
    for s in all_sites:
        sites.setdefault(s, {'site': s, 'monitored': False, 'reason': '尚未掃描'})
    if mode == 'bootstrap':
        best = {}
        for fn in sys.argv[2:]:
            for l in open(fn):
                r = json.loads(l); p = best.get(r['site'])
                rank = lambda x: (site_verdict(x)[0], x['status'] == 'ok', len(x.get('items', [])))
                if p is None or rank(r) > rank(p): best[r['site']] = r
        results = [best[s] for s in all_sites if s in best]
        full = True
    elif mode == 'rejudge':
        results, full = [], False
    else:
        full = mode == 'full'
        todo = all_sites if full else [s for s in all_sites if sites.get(s, {}).get('monitored') or sites.get(s, {}).get('reason') == '尚未掃描']
        browser_sites = {s for s in todo if sites.get(s, {}).get('browser')}
        print(mode, 'sites to crawl:', len(todo), flush=True)
        results = run_crawl(todo, browser_sites)
    new = merge(sites, tenders, results, full, dropped)
    if mode == 'bootstrap':
        for t in tenders.values(): t['baseline'] = True
    todo_detail = [t for t in tenders.values() if not t.get('detail_checked')]
    if ai.KEY:
        todo_detail += [t for t in tenders.values() if needs_ai(t)][:AI_BACKFILL]
    print('new tenders', len(new), 'detail fetch', len(todo_detail), flush=True)
    with cf.ThreadPoolExecutor(16) as ex: list(ex.map(extract_detail, todo_detail))
    prune(tenders, dropped)
    new = [t for t in new if t['id'] in tenders]
    backup_run = None
    if r2.enabled():
        todo_backup = [t for t in tenders.values() if t.get('doc') and t.get('active', True) and not t.get('backup')
                       and t.get('backup_tries', 0) < r2.MAX_TRIES]
        print('PDF backup', len(todo_backup), flush=True)
        with cf.ThreadPoolExecutor(8) as ex: states = list(ex.map(lambda t: r2.backup(t, TODAY), todo_backup))
        backup_run = {k: states.count(k) for k in ('ok', 'dead', 'school', 'sys')}
        backup_run['tried'] = len(states)
        sys_msgs = sorted({t['backup_error'] for t in todo_backup if t.get('backup_state') == 'sys'})
        if sys_msgs: backup_run['sys_msg'] = '；'.join(sys_msgs[:3])
        print('PDF backup', backup_run, flush=True)
        prune(tenders, dropped)
    if backup_run is not None and PRUNE_FAILED:
        backup_run['sys'] = backup_run.get('sys', 0) + len(PRUNE_FAILED)
        backup_run['sys_msg'] = '；'.join(filter(None, [backup_run.get('sys_msg'), f'刪除 {len(PRUNE_FAILED)} 個 R2 舊檔失敗']))
    if backup_run is None and os.environ.get('GITHUB_ACTIONS'):
        backup_run = {'tried': 0, 'ok': 0, 'dead': 0, 'school': 0, 'sys': 1, 'sys_msg': 'GitHub 未設定 Cloudflare R2 鑰匙'}
    counts = {}
    for t in tenders.values(): counts[t['site']] = counts.get(t['site'], 0) + 1
    for s in sites.values(): s['tender_count'] = counts.get(s['site'], 0)
    save('schools.json', schools)
    save('dropped.json', dropped)
    save('sites.json', sorted(sites.values(), key=lambda s: s['site']))
    for t in tenders.values():
        if t.get('published', '') > TODAY or (t.get('deadline') and t.get('published', '') > t['deadline']):
            t.pop('published', None); t.pop('published_src', None)
    save('tenders.json', sorted(tenders.values(), key=lambda t: (t['first_seen'], t.get('published') or ''), reverse=True))
    print('gemini', ai.STATS, flush=True)
    if mode == 'rejudge': return
    meta = load('meta.json', {'runs': []})
    run = {'at': NOW, 'mode': mode, 'sites_checked': len(results), 'ok': sum(r['status'] == 'ok' for r in results),
           'new_tenders': len(new), 'new_eng': sum(bool(t['eng_types']) for t in new), 'seconds': round(time.time() - t0)}
    if backup_run: run['backup'] = backup_run
    if ai.KEY: run['ai'] = dict(ai.STATS)
    meta['runs'] = ([run] + meta.get('runs', []))[:60]
    meta['updated_at'] = NOW
    save('meta.json', meta)
    print(json.dumps(run, ensure_ascii=False))

if __name__ == '__main__':
    main()
