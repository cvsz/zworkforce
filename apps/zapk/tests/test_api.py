import os
import tempfile
os.environ['ZEAZ_DATA_DIR']=tempfile.mkdtemp()
os.environ['ZEAZ_ADMIN_TOKEN']='test-secret'
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)

def test_catalogue():
    assert client.get('/api/health').json()['status']=='ok'
    assert client.get('/api/apps').json()['total']>=4
    assert client.get('/api/apps?type=game').json()['total']>=1

def test_resolver():
    d=client.get('/api/resolve',params={'value':'https://play.google.com/store/apps/details?id=dev.zeaz.demo&hl=en'}).json()
    assert d['package']=='dev.zeaz.demo' and d['found']
    assert client.get('/api/resolve',params={'value':'https://evil.test/?id=dev.zeaz.demo'}).status_code==400

def test_admin():
    payload={'package':'org.example.test','name':'Test','developer':'Publisher'}
    assert client.post('/api/publisher/apps',json=payload).status_code==401
    assert client.post('/api/publisher/apps',json=payload,headers={'Authorization':'Bearer test-secret'}).status_code==200
    assert client.get('/api/apps/org.example.test').status_code==200

def test_file_validation():
    headers={'Authorization':'Bearer test-secret'}
    bad=client.post('/api/publisher/apps/org.example.test/builds',data={'version':'1.0'},files={'file':('bad.apk',b'invalid bytes')},headers=headers)
    assert bad.status_code==400
