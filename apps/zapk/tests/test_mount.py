from fastapi.testclient import TestClient
from app.main import root_app
client=TestClient(root_app)

def test_mount():
    assert client.get('/zapk/api/health').json()['status']=='ok'
    assert client.get('/zapk/').status_code == 200
    assert client.get('/zapk/docs').status_code == 200
    assert client.get('/api/health').status_code == 404

def test_no_unauthorized_approval():
    assert client.post('/zapk/api/publisher/builds/1/approve').status_code == 401
