"""Back up tender PDFs/attachments to Cloudflare R2 (bucket school-tender-pdfs).

Env: R2_ENDPOINT plus either R2_ACCESS_KEY_ID + R2_SECRET_ACCESS_KEY, or R2_API_TOKEN
(a Cloudflare API token; its S3 key pair is derived: id = token id, secret = sha256(token)).
"""
import os, re, hashlib, json, urllib.request
from urllib.parse import unquote
import crawl

BUCKET = os.environ.get('R2_BUCKET', 'school-tender-pdfs')
MAX_BYTES = 25_000_000
EXT = re.compile(r'\.(pdf|docx?|xlsx?|pptx?|zip|rar|jpe?g|png)$', re.I)
TYPES = {'pdf': 'application/pdf', 'doc': 'application/msword', 'xls': 'application/vnd.ms-excel',
         'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'zip': 'application/zip'}
_client = None

def _keys():
    kid, sec, tok = (os.environ.get(k, '').strip() for k in ('R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_API_TOKEN'))
    if kid.startswith('cfat_') and not tok: tok, kid = kid, ''
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

def backup(t, today):
    """Download t['url'] and store it in R2; sets t['backup'] (object key)."""
    try:
        r = crawl.sess().get(t['url'], timeout=(8, 60), stream=True)
        if r.status_code >= 400:
            t['backup_error'] = f'HTTP {r.status_code}'; return
        data = r.raw.read(MAX_BYTES + 1, decode_content=True)
        if len(data) > MAX_BYTES:
            t['backup_error'] = '檔案太大'; return
        if data[:15].lstrip().lower().startswith((b'<!doctype', b'<html')):
            t['backup_error'] = '不是檔案'; return
        m = EXT.search(unquote(t['url']).split('?')[0])
        ext = 'pdf' if data[:4] == b'%PDF' else (m.group(1).lower() if m else 'bin')
        key = f"pdf/{today[:7]}/{t['id']}.{ext}"
        client().put_object(Bucket=BUCKET, Key=key, Body=data,
                            ContentType=TYPES.get(ext, r.headers.get('content-type') or 'application/octet-stream'),
                            Metadata={'source': t['url'][:1000].encode('ascii', 'ignore').decode()})
        t['backup'] = key; t['backup_at'] = today; t['backup_size'] = len(data)
        t.pop('backup_error', None)
    except Exception as e:
        t['backup_error'] = type(e).__name__
