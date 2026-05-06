from fastapi.testclient import TestClient

import app.state as state
from app.main import app
from app.security import hash_admin_password


client = TestClient(app, raise_server_exceptions=True)


def setup_function():
    state.clear_admin_login_attempts()


def test_admin_login_with_hashed_password(monkeypatch):
    monkeypatch.setattr('app.config.settings.admin_username', 'admin')
    monkeypatch.setattr('app.config.settings.admin_password_hash', hash_admin_password('S3cureP@ss!'))

    resp = client.post('/auth/admin/login', json={'username': 'admin', 'password': 'S3cureP@ss!'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'access_token' in data
    assert data['token_type'] == 'bearer'


def test_admin_login_rejects_invalid_password(monkeypatch):
    monkeypatch.setattr('app.config.settings.admin_username', 'admin')
    monkeypatch.setattr('app.config.settings.admin_password_hash', hash_admin_password('S3cureP@ss!'))

    resp = client.post('/auth/admin/login', json={'username': 'admin', 'password': 'wrong-pass'})
    assert resp.status_code == 401


def test_admin_login_requires_hash_config(monkeypatch):
    monkeypatch.setattr('app.config.settings.admin_username', 'admin')
    monkeypatch.setattr('app.config.settings.admin_password_hash', '')

    resp = client.post('/auth/admin/login', json={'username': 'admin', 'password': 'anything'})
    assert resp.status_code == 503


def test_admin_login_rate_limited_after_repeated_failures(monkeypatch):
    monkeypatch.setattr('app.config.settings.admin_username', 'admin')
    monkeypatch.setattr('app.config.settings.admin_password_hash', hash_admin_password('S3cureP@ss!'))
    monkeypatch.setattr('app.config.settings.admin_login_max_attempts', 3)
    monkeypatch.setattr('app.config.settings.admin_login_window_seconds', 60)
    monkeypatch.setattr('app.config.settings.admin_login_lockout_seconds', 120)

    now = [1_000_000]
    monkeypatch.setattr('app.state._now_ts', lambda: now[0])

    for _ in range(2):
        resp = client.post('/auth/admin/login', json={'username': 'admin', 'password': 'wrong'})
        assert resp.status_code == 401

    blocked = client.post('/auth/admin/login', json={'username': 'admin', 'password': 'wrong'})
    assert blocked.status_code == 429
    assert blocked.headers.get('Retry-After') == '120'

    still_blocked = client.post('/auth/admin/login', json={'username': 'admin', 'password': 'S3cureP@ss!'})
    assert still_blocked.status_code == 429


def test_admin_login_rate_limit_expires(monkeypatch):
    monkeypatch.setattr('app.config.settings.admin_username', 'admin')
    monkeypatch.setattr('app.config.settings.admin_password_hash', hash_admin_password('S3cureP@ss!'))
    monkeypatch.setattr('app.config.settings.admin_login_max_attempts', 2)
    monkeypatch.setattr('app.config.settings.admin_login_window_seconds', 60)
    monkeypatch.setattr('app.config.settings.admin_login_lockout_seconds', 30)

    now = [2_000_000]
    monkeypatch.setattr('app.state._now_ts', lambda: now[0])

    assert client.post('/auth/admin/login', json={'username': 'admin', 'password': 'wrong'}).status_code == 401
    assert client.post('/auth/admin/login', json={'username': 'admin', 'password': 'wrong'}).status_code == 429

    now[0] += 31
    ok = client.post('/auth/admin/login', json={'username': 'admin', 'password': 'S3cureP@ss!'})
    assert ok.status_code == 200
