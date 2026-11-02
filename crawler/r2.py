"""Back up tender PDFs/attachments to Cloudflare R2 (bucket school-tender-pdfs).

Env: R2_ENDPOINT plus either R2_ACCESS_KEY_ID + R2_SECRET_ACCESS_KEY, or R2_API_TOKEN
(a Cloudflare API token; its S3 key pair is derived: id = token id, secret = sha256(token)).

backup() sets t['backup_state']:
  ok     - stored; t['backup'] is the object key
  dead   - school link no longer gives a file (PDF已失效)
  school - school site slow / blocked / erroring; retried up to MAX_TRIES runs
  sys    - our side (R2 / credentials / size limit); retried every run, not counted
"""
import os, re, hashlib, json, urllib.request
from urllib.parse import unquote
import requests
import crawl

BUCKET = os.environ.get('R2_BUCKET', 'school-tender-pdfs')
MAX_BYTES = 100_000_000
MAX_TRIES = 3
EXT = re.compile(r'\.(pdf|docx?|xlsx?|pptx?|zip|rar|jpe?g|png)$', re.I)
TYPES = {'pdf': 'application/pdf', 'doc': 'application/msword', 'xls': 'application/vnd.ms-excel',
         'ppt': 'application/vnd.ms-powerpoint', 'zip': 'application/zip', 'rar': 'application/vnd.rar',
         'jpg': 'image/jpeg', 'png': 'image/png',
         'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
         'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'}
_client = None


def _keys():
    kid, sec, tok = (os.environ.get(k, '').strip() for k in ('R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_API_TOKEN'))
    if kid.startswith('cfat_') and not tok:
        tok, kid = kid, ''
    if tok and not (kid and sec):
        acct = endpoint().split('//')[-1].split('.')[0]
        req = urllib.request.Request(f'https://api.cloudflare.com/client/v4/accounts/{acct}/tokens/verify',
                                     headers={'Authorization': 'Bearer ' + tok})
        kid = json.load(urllib.request.urlopen(req, timeout=20))['result']['id']
        sec = hashlib.sha256(tok.encode()).hexdigest()
    return kid, sec


def endpoint():
    ep = os.environ.get('R2_ENDPOINT', '').strip()
    return ep.split('//')[0] + '//' + ep.split('//')[-1].split('/')[0] if ep else ''


def client():
    global _client
    if _client is None:
        import boto3
        kid, sec = _keys()
        _client = boto3.client('s3', endpoint_url=endpoint(), aws_access_key_id=kid,
                               aws_secret_access_key=sec, region_name='auto')
    return _client


def enabled():
    return bool(endpoint() and (os.environ.get('R2_API_TOKEN') or os.environ.get('R2_SECRET_ACCESS_KEY')))


def sniff(data, url_ext):
    """File type from content signature, or None if it is not a real file."""
    head = data[:8]
    if b'%PDF-' in data[:1024]: return 'pdf'
    if head.startswith(b'PK\x03\x04'): return url_ext if url_ext in ('docx', 'xlsx', 'pptx') else 'zip'
    if head.startswith(b'\xd0\xcf\x11\xe0'): return url_ext if url_ext in ('doc', 'xls', 'ppt') else 'doc'
    if head.startswith(b'Rar!'): return 'rar'
    if head.startswith(b'\xff\xd8\xff'): return 'jpg'
    if head.startswith(b'\x89PNG'): return 'png'
    return None


def _fail(t, state, msg):
    t['backup_state'], t['backup_error'] = state, msg
    if state != 'sys':
        t['backup_tries'] = t.get('backup_tries', 0) + 1
    return state


def download(url):
    """Returns (data, None) or (None, (state, message))."""
    try:
        r = crawl.sess().get(url, timeout=(10, 60), stream=True, allow_redirects=True)
    except requests.Timeout:
        return None, ('school', '學校網站太慢，下載逾時')
    except requests.RequestException:
        return None, ('school', '學校網站無法連線')
    with r:
        if r.status_code in (404, 410):
            return None, ('dead', 'PDF已失效（學校網站找不到檔案）')
        if r.status_code in (401, 403, 429):
            return None, ('school', '學校網站阻擋下載')
        if r.status_code >= 400:
            return None, ('school', f'學校網站出錯（HTTP {r.status_code}）')
        try:
            data = r.raw.read(MAX_BYTES + 1, decode_content=True)
        except Exception:
            return None, ('school', '下載中途中斷')
    if len(data) > MAX_BYTES:
        return None, ('sys', f'檔案超過 {MAX_BYTES // 1_000_000} MB 上限')
    return data, None


def backup(t, today):
    """Download t['url'] and store it in R2. Returns the resulting backup_state."""
    data, err = download(t['url'])
    if err:
        return _fail(t, *err)
    m = EXT.search(unquote(t['url']).split('?')[0].split('#')[0])
    ext = sniff(data, m.group(1).lower() if m else '')
    if not ext:
        text = data[:4096].lower()
        why = '連結只打開網頁，沒有檔案' if (b'<html' in text or b'<!doctype' in text or b'<body' in text) \
            else '檔案是空的' if not data.strip() else '內容不是有效檔案'
        return _fail(t, 'dead', f'PDF已失效（{why}）')
    key = f"pdf/{today[:7]}/{t['id']}.{ext}"
    try:
        client().put_object(Bucket=BUCKET, Key=key, Body=data, ContentType=TYPES.get(ext, 'application/octet-stream'),
                            Metadata={'source': t['url'][:1000].encode('ascii', 'ignore').decode()})
    except Exception as e:
        code = getattr(e, 'response', {}).get('Error', {}).get('Code', '') if hasattr(e, 'response') else ''
        return _fail(t, 'sys', f'Cloudflare 儲存失敗（{code or type(e).__name__}）')
    t.update(backup=key, backup_at=today, backup_size=len(data), backup_state='ok')
    t.pop('backup_error', None)
    return 'ok'


def delete(key):
    try:
        client().delete_object(Bucket=BUCKET, Key=key)
        return True
    except Exception as e:
        print('R2 delete failed', key, type(e).__name__, flush=True)
        return False
