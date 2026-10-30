import os
import tempfile
from pathlib import Path
os.environ['ZEAZ_DATA_DIR']=tempfile.mkdtemp()
os.environ['ZEAZ_ADMIN_TOKEN']='test-secret'
from fastapi.testclient import TestClient
from app.main import app, _validate_production_secrets
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


def test_example_environment_uses_placeholders():
    env_path = Path(__file__).resolve().parents[1] / '.env.zapk.example'
    values = {}
    for line in env_path.read_text(encoding='utf-8').splitlines():
        if line and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key] = value
    assert values['ZEAZ_ADMIN_TOKEN'] == 'replace-with-long-random-secret'
    assert values['ZEAZ_SIGNING_SECRET'] == 'replace-with-another-long-random-secret'
    assert values['ZEAZ_ADMIN_TOKEN'] != values['ZEAZ_SIGNING_SECRET']

def test_production_rejects_example_secret_placeholders():
    valid_secret = 'v' * 48
    invalid_pairs = (
        ('replace-with-long-random-secret', valid_secret),
        (valid_secret, 'replace-with-another-long-random-secret'),
    )
    for admin_token, signing_secret in invalid_pairs:
        try:
            _validate_production_secrets(admin_token, signing_secret)
        except RuntimeError:
            continue
        raise AssertionError('Production secret validation accepted an example placeholder')


def test_production_accepts_distinct_generated_secrets():
    _validate_production_secrets('a' * 48, 'b' * 48)
