import pytest
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from app.server import app, init_db, get_db_connection





@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def setup_db():
    init_db()

    db_conn = get_db_connection()
    db_conn.execute('DELETE FROM todo')
    db_conn.commit()


def test_can_list_todos(client):
    todo_title = _add_todo(client, "abc 123")

    response = client.get('/')
    assert response.status_code == 200
    assert todo_title in response.text


def _add_todo(client, todo_title):
    client.post(
        '/add',
        json={
            'title': todo_title
        }
    )

    return todo_title
