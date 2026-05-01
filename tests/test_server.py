import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent))


@pytest.fixture
def client(monkeypatch):
    """Fresh app with an isolated SQLite DB for each test."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    os.environ['DATABASE_PATH'] = path

    # Re-import so server picks up the new DATABASE_PATH
    if 'app.server' in sys.modules:
        del sys.modules['app.server']
    if 'app' in sys.modules:
        del sys.modules['app']

    from app.server import app, init_db
    init_db()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.test_client() as c:
        yield c

    try:
        os.remove(path)
    except OSError:
        pass


def _register_and_login(client, username='alice', email='alice@example.com', password='secret123'):
    client.post('/register', data={'username': username, 'email': email, 'password': password})
    client.post('/login', data={'username': username, 'password': password})


def test_register_and_login(client):
    rv = client.post('/register', data={
        'username': 'bob', 'email': 'bob@example.com', 'password': 'pass1234'
    }, follow_redirects=True)
    assert rv.status_code == 200

    rv = client.post('/login', data={'username': 'bob', 'password': 'pass1234'}, follow_redirects=True)
    assert rv.status_code == 200
    # Logged-in nav exposes the username
    assert b'bob' in rv.data


def test_login_required_redirects(client):
    rv = client.get('/', follow_redirects=False)
    assert rv.status_code == 302
    assert '/login' in rv.headers['Location']


def test_add_and_list_todo(client):
    _register_and_login(client)

    rv = client.post('/add', data={
        'title': 'Buy groceries',
        'description': 'milk, bread',
        'priority': '3',
        'due_date': '',
        'category_id': '',
    }, follow_redirects=True)
    assert rv.status_code == 200
    assert b'Buy groceries' in rv.data

    rv = client.get('/')
    assert b'Buy groceries' in rv.data
    assert b'milk, bread' in rv.data


def test_complete_toggle(client):
    _register_and_login(client)
    client.post('/add', data={'title': 'Workout', 'priority': '2'})

    # Find the task ID from the index page (1, since fresh DB)
    rv = client.post('/complete/1', follow_redirects=True)
    assert rv.status_code == 200

    # When status filter = active, completed task is hidden
    rv = client.get('/?status=active')
    assert b'Workout' not in rv.data

    rv = client.get('/?status=completed')
    assert b'Workout' in rv.data


def test_edit_todo(client):
    _register_and_login(client)
    client.post('/add', data={'title': 'Old title', 'priority': '2'})

    rv = client.post('/edit/1', data={
        'title': 'New title',
        'description': 'updated',
        'priority': '1',
        'due_date': '',
        'category_id': '',
    }, follow_redirects=True)
    assert rv.status_code == 200
    assert b'New title' in rv.data
    assert b'Old title' not in rv.data


def test_delete_todo(client):
    _register_and_login(client)
    client.post('/add', data={'title': 'Temporary', 'priority': '2'})
    rv = client.post('/delete/1', follow_redirects=True)
    assert b'Temporary' not in rv.data


def test_search_filter(client):
    _register_and_login(client)
    client.post('/add', data={'title': 'Pay rent', 'priority': '2'})
    client.post('/add', data={'title': 'Call mom', 'priority': '2'})

    rv = client.get('/?search_query=rent')
    assert b'Pay rent' in rv.data
    assert b'Call mom' not in rv.data


def test_priority_filter(client):
    _register_and_login(client)
    client.post('/add', data={'title': 'High thing', 'priority': '3'})
    client.post('/add', data={'title': 'Low thing', 'priority': '1'})

    rv = client.get('/?priority=3&status=all')
    assert b'High thing' in rv.data
    assert b'Low thing' not in rv.data


def test_users_isolated(client):
    # User A creates a task
    _register_and_login(client, username='alice', email='a@a.com', password='aaaaaaa')
    client.post('/add', data={'title': "Alice's secret", 'priority': '2'})
    client.post('/logout')

    # User B should not see it
    _register_and_login(client, username='betty', email='b@b.com', password='bbbbbbb')
    rv = client.get('/?status=all')
    assert b"Alice's secret" not in rv.data


def test_categories_seeded_on_register(client):
    _register_and_login(client)
    rv = client.get('/categories')
    assert b'Work' in rv.data
    assert b'Personal' in rv.data


def test_dashboard_loads(client):
    _register_and_login(client)
    client.post('/add', data={'title': 'A', 'priority': '2'})
    client.post('/complete/1')
    rv = client.get('/dashboard')
    assert rv.status_code == 200
    assert b'Dashboard' in rv.data
