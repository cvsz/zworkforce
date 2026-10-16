import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import zipfile
import logging
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('ZEAZ_DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
FILES = DATA / 'packages'
FILES.mkdir(exist_ok=True)
DB = DATA / 'catalog.db'
SECRET = os.environ.get('ZEAZ_SIGNING_SECRET', '') or secrets.token_hex(32)
ADMIN_TOKEN = os.environ.get('ZEAZ_ADMIN_TOKEN', '')
APKCUBE_API_KEY = os.environ.get('APKCUBE_API_KEY', '')
MAX_UPLOAD = int(os.environ.get('ZEAZ_MAX_UPLOAD_BYTES', str(150 * 1024 * 1024)))
PUBLIC_BASE_PATH = os.environ.get('ZEAZ_BASE_PATH', '/zapk').rstrip('/')
if not PUBLIC_BASE_PATH.startswith('/') or PUBLIC_BASE_PATH == '/' or not re.fullmatch(r'/[a-zA-Z0-9_-]+', PUBLIC_BASE_PATH):
    raise RuntimeError('ZEAZ_BASE_PATH must be a single path segment such as /zapk')
if os.environ.get('ZEAZ_ENV') == 'production':
    if not os.environ.get('ZEAZ_SIGNING_SECRET') or len(ADMIN_TOKEN) < 32 or len(SECRET) < 32 or ADMIN_TOKEN == SECRET:
        raise RuntimeError('Production requires distinct ZEAZ_ADMIN_TOKEN and ZEAZ_SIGNING_SECRET of at least 32 characters')
PACKAGE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$')
app = FastAPI(title='ZEAZ APK Hub', version='0.2.0', docs_url='/docs', redoc_url=None)
logging.basicConfig(level=os.getenv('ZEAZ_LOG_LEVEL', 'INFO'))

@contextmanager
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

with db() as c:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS apps (package TEXT PRIMARY KEY, name TEXT NOT NULL, developer TEXT NOT NULL,
      category TEXT NOT NULL, type TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', icon TEXT NOT NULL DEFAULT '',
      installs TEXT NOT NULL DEFAULT '—', rating REAL, source TEXT NOT NULL DEFAULT 'publisher');
    CREATE TABLE IF NOT EXISTS builds (id INTEGER PRIMARY KEY AUTOINCREMENT, package TEXT NOT NULL REFERENCES apps(package),
      version TEXT NOT NULL, file_name TEXT NOT NULL, format TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
      size INTEGER NOT NULL, created INTEGER NOT NULL);
    ''')
    if 'approved' not in [x[1] for x in c.execute('PRAGMA table_info(builds)')]:
        c.execute('ALTER TABLE builds ADD COLUMN approved INTEGER NOT NULL DEFAULT 0')
    if not c.execute('SELECT count(*) FROM apps').fetchone()[0]:
        samples = [
          ('dev.zeaz.demo','ZEAZ Demo','ZEAZDEV','Tools','app','Demonstration catalogue item, not an installable release.','', '—',None,'demo'),
          ('dev.zeaz.workspace','ZEAZ Workspace','ZEAZDEV','Productivity','app','Example listing for catalog navigation.','', '—',None,'demo'),
          ('dev.zeaz.arcade','ZEAZ Arcade','ZEAZDEV','Arcade','game','Example game listing.','', '—',None,'demo'),
          ('dev.zeaz.secure','ZEAZ Secure','ZEAZDEV','Security','app','Example security tool listing.','', '—',None,'demo')]
        c.executemany('INSERT INTO apps VALUES (?,?,?,?,?,?,?,?,?,?)',samples)

def parse_package(value: str) -> str:
    v = value.strip()
    if v.startswith('https://'):
        u = urlparse(v)
        if u.netloc not in ('play.google.com', 'www.play.google.com') or u.path != '/store/apps/details':
            raise HTTPException(400, 'Only Google Play app URLs are supported')
        v = parse_qs(u.query).get('id', [''])[0]
    if not PACKAGE_RE.fullmatch(v) or len(v) > 200:
        raise HTTPException(400, 'Invalid Android package identifier')
    return v

def app_view(row, c):
    d = dict(row)
    build = c.execute('SELECT version, format, sha256, size, created FROM builds WHERE package=? AND approved=1 ORDER BY created DESC,id DESC LIMIT 1',(d['package'],)).fetchone()
    d['latest'] = dict(build) if build else None
    d['hasFiles'] = bool(build)
    return d

@app.get('/api/health')
def health():
    return {'status':'ok','service':'zeaz-apk-hub'}

@app.get('/api/categories')
def categories():
    with db() as c:
        return {'items':[dict(r) for r in c.execute('SELECT category AS name,type,count(*) AS count FROM apps GROUP BY category,type ORDER BY count DESC,name')]}

@app.get('/api/apps')
def list_apps(q: str = '', type: str = '', category: str = '', sort: str = 'name', page: int = Query(1, ge=1), size: int = Query(24, ge=1, le=48)):
    if type not in ('','app','game') or sort not in ('name','recent','rating'):
        raise HTTPException(400,'Invalid filter')
    where = ['1=1']; args = []
    if q:
        where.append('(name LIKE ? OR developer LIKE ? OR package LIKE ?)')
        term = '%' + q[:100].replace('%','\\%').replace('_','\\_') + '%'
        where[-1] = where[-1].replace(' LIKE ?', " LIKE ? ESCAPE '\\'")
        args.extend([term]*3)
    if type:
        where.append('type=?'); args.append(type)
    if category:
        where.append('category=?'); args.append(category)
    order = {'name':'name COLLATE NOCASE','recent':'rowid DESC','rating':'rating DESC NULLS LAST'}[sort]
    with db() as c:
        cond = ' AND '.join(where)
        count = c.execute('SELECT count(*) FROM apps WHERE '+cond,args).fetchone()[0]
        rows = c.execute(f'SELECT * FROM apps WHERE {cond} ORDER BY {order} LIMIT ? OFFSET ?',args+[size,(page-1)*size]).fetchall()
        return {'items':[app_view(x,c) for x in rows],'total':count,'page':page,'pages':(count+size-1)//size}

@app.get('/api/apps/{package}')
def detail(package: str):
    package = parse_package(package)
    with db() as c:
        row = c.execute('SELECT * FROM apps WHERE package=?',(package,)).fetchone()
        if not row: raise HTTPException(404,'App not found')
        return app_view(row,c)

@app.get('/api/apps/{package}/versions')
def versions(package: str):
    package = parse_package(package)
    with db() as c:
        return {'items':[dict(x) for x in c.execute('SELECT id,version,format,sha256,size,created,approved FROM builds WHERE package=? ORDER BY created DESC,id DESC',(package,))]}

@app.get('/api/resolve')
def resolve(value: str):
    package = parse_package(value)
    with db() as c:
        r=c.execute('SELECT * FROM apps WHERE package=?',(package,)).fetchone()
        return {'package':package,'found':bool(r),'app':app_view(r,c) if r else None,
                'playUrl':f'https://play.google.com/store/apps/details?id={package}'}

class Listing(BaseModel):
    package: str
    name: str
    developer: str
    category: str = 'Tools'
    type: str = 'app'
    description: str = ''
    icon: str = ''

def require_admin(authorization: str):
    if not ADMIN_TOKEN:
        raise HTTPException(503,'Publisher writes disabled: set ZEAZ_ADMIN_TOKEN')
    if not authorization.startswith('Bearer ') or not hmac.compare_digest(authorization[7:], ADMIN_TOKEN):
        raise HTTPException(401,'Unauthorized')

@app.post('/api/publisher/apps')
def publish(item: Listing, authorization: str = Header('')):
    require_admin(authorization)
    pkg=parse_package(item.package)
    if item.type not in ('app','game'): raise HTTPException(400,'Invalid type')
    if item.icon and not item.icon.startswith('https://'): raise HTTPException(400,'Icon URL must use HTTPS')
    with db() as c:
        c.execute('''INSERT INTO apps(package,name,developer,category,type,description,icon,source)
          VALUES(?,?,?,?,?,?,?, 'publisher') ON CONFLICT(package) DO UPDATE SET
          name=excluded.name,developer=excluded.developer,category=excluded.category,type=excluded.type,
          description=excluded.description,icon=excluded.icon''',
          (pkg,item.name[:160],item.developer[:160],item.category[:80],item.type,item.description[:6000],item.icon))
    return {'package':pkg,'saved':True}

@app.post('/api/publisher/apps/{package}/builds')
async def upload(package: str, version: str = Form(...), file: UploadFile = File(...), authorization: str = Header('')):
    require_admin(authorization)
    package=parse_package(package)
    suffix=Path(file.filename or '').suffix.lower().lstrip('.')
    if suffix not in ('apk','apks','xapk'): raise HTTPException(400,'Only APK/APKS/XAPK files are supported')
    with db() as c:
        if not c.execute('SELECT 1 FROM apps WHERE package=?',(package,)).fetchone(): raise HTTPException(404,'Publish listing first')
    temp=FILES / (secrets.token_hex(20)+'.tmp')
    digest=hashlib.sha256(); size=0
    try:
        with temp.open('wb') as out:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>MAX_UPLOAD: raise HTTPException(413,'File exceeds 150 MiB')
                digest.update(chunk);out.write(chunk)
        if size<4: raise HTTPException(400,'Empty/invalid file')
        with temp.open('rb') as f: sig=f.read(4)
        if suffix=='apk' and sig!=b'PK\x03\x04': raise HTTPException(400,'APK must be a ZIP container')
        if suffix in ('apks','xapk') and sig!=b'PK\x03\x04': raise HTTPException(400,'Bundle must be a ZIP container')
        try:
            with zipfile.ZipFile(temp) as archive:
                contents=archive.infolist()
                if len(contents)>10000 or sum(x.file_size for x in contents)>1024*1024*1024:
                    raise HTTPException(400,'Archive exceeds validation limits')
                if not any(x.filename.endswith('AndroidManifest.xml') for x in contents) and suffix=='apk':
                    raise HTTPException(400,'APK has no AndroidManifest.xml')
                if any(x.filename.startswith('/') or '..' in Path(x.filename).parts for x in contents):
                    raise HTTPException(400,'Unsafe archive paths')
                if archive.testzip() is not None:
                    raise HTTPException(400,'Corrupt archive')
        except zipfile.BadZipFile:
            raise HTTPException(400,'Invalid ZIP archive')
        sha=digest.hexdigest(); destination=FILES/(sha+'.'+suffix)
        temp.replace(destination)
        with db() as c:
            c.execute('INSERT OR IGNORE INTO builds(package,version,file_name,format,sha256,size,created) VALUES(?,?,?,?,?,?,?)',
                      (package,version[:80],destination.name,suffix,sha,size,int(time.time())))
        return {'sha256':sha,'size':size,'format':suffix,'approved':False,'warning':'Build quarantined until an administrator approves it. Malware and signing validation are NOT performed.'}
    finally:
        temp.unlink(missing_ok=True)
        await file.close()

def signature(build_id: int, expires: int) -> str:
    return hmac.new(SECRET.encode(),f'{build_id}:{expires}'.encode(),hashlib.sha256).hexdigest()

@app.post('/api/apps/{package}/download/{build_id}')
def download_link(package: str,build_id: int):
    package=parse_package(package)
    with db() as c:
        row=c.execute('SELECT * FROM builds WHERE id=? AND package=?',(build_id,package)).fetchone()
        if not row: raise HTTPException(404,'Build not found')
        if not row['approved']: raise HTTPException(403,'Build pending manual review')
    exp=int(time.time())+300
    return {'url':f'/api/files/{build_id}?expires={exp}&signature={signature(build_id,exp)}',
            'expires':exp,'sha256':row['sha256'],'format':row['format']}

@app.get('/api/files/{build_id}')
def get_file(build_id: int, expires: int, signature: str):
    if expires<int(time.time()) or expires>int(time.time())+3600 or not hmac.compare_digest(signature,signature_for(build_id,expires)):
        raise HTTPException(403,'Invalid or expired download link')
    with db() as c:
        row=c.execute('SELECT * FROM builds WHERE id=?',(build_id,)).fetchone()
    if not row: raise HTTPException(404,'Build not found')
    if not row['approved']: raise HTTPException(403,'Build pending manual review')
    return FileResponse(FILES/row['file_name'],filename=f"{row['package']}-{row['version']}.{row['format']}")

def signature_for(build_id,expires):
    return signature(build_id,expires)

@app.get('/api/lookup/hash/{sha}')
def hash_lookup(sha: str):
    if not re.fullmatch('[0-9a-fA-F]{64}',sha): raise HTTPException(400,'Invalid SHA-256')
    with db() as c:
        row=c.execute('SELECT package,version,format,size,created FROM builds WHERE sha256=?',(sha.lower(),)).fetchone()
        return {'found':bool(row),'build':dict(row) if row else None}

@app.get('/api/integrations/apkcube/search')
async def external_search(q: str):
    if not APKCUBE_API_KEY: raise HTTPException(503,'External integration disabled: set APKCUBE_API_KEY')
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r=await client.get('https://apkcube.com/api/v1/apps',params={'q':q[:100]},headers={'Authorization':f'Bearer {APKCUBE_API_KEY}'})
        except httpx.HTTPError: raise HTTPException(502,'Upstream unavailable')
    if r.status_code != 200: raise HTTPException(r.status_code,'Upstream request failed')
    return {'data':r.json(),'creditsCost':r.headers.get('x-credits-cost'),'creditsRemaining':r.headers.get('x-credits-remaining')}

app.mount('/assets',StaticFiles(directory=ROOT/'app'/'static'),name='assets')
@app.get('/')
def index():return FileResponse(ROOT/'app'/'static'/'index.html')


@app.post('/api/publisher/builds/{build_id}/approve')
def approve_build(build_id: int, authorization: str = Header('')):
    require_admin(authorization)
    with db() as c:
        row = c.execute('SELECT id FROM builds WHERE id=?', (build_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Build not found')
        c.execute('UPDATE builds SET approved=1 WHERE id=?', (build_id,))
    return {'id': build_id, 'approved': True, 'warning': 'Approval does not certify package safety'}


# ASGI mount keeps all browser and API paths under /zapk, independent of proxy rewriting.
from fastapi import FastAPI as RootFastAPI
root_app = RootFastAPI(docs_url=None, redoc_url=None, openapi_url=None)
root_app.mount(PUBLIC_BASE_PATH, app)
