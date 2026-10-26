import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app import app
from database.db import get_db, init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("database.db.DB_PATH", str(tmp_path / "test.db"))
    init_db()
    app.config["TESTING"] = True
    return app.test_client()


def all_users():
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM users").fetchall()
    finally:
        conn.close()


def post(client, name="Asha Rao", email="asha@example.com", password="secret123"):
    return client.post(
        "/register", data={"name": name, "email": email, "password": password}
    )


def test_get_register_renders_form(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Create your account" in response.data


def test_valid_registration_redirects_to_login(client):
    response = post(client, name="  Asha Rao  ", email="  Asha@Example.COM ")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    users = all_users()
    assert len(users) == 1
    assert users[0]["name"] == "Asha Rao"
    assert users[0]["email"] == "asha@example.com"
    assert users[0]["password_hash"] != "secret123"
    assert check_password_hash(users[0]["password_hash"], "secret123")


@pytest.mark.parametrize("email", ["asha@example.com", "ASHA@Example.com"])
def test_duplicate_email_rejected(client, email):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Existing", "asha@example.com", generate_password_hash("whatever1")),
    )
    conn.commit()
    conn.close()

    response = post(client, email=email)
    assert response.status_code == 200
    assert b"already exists" in response.data
    assert len(all_users()) == 1


def test_short_password_rejected(client):
    response = post(client, password="short12")
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data
    assert all_users() == []


@pytest.mark.parametrize("email", ["foo", "foo@", "@x.com", "a@b", "a@b.", "a@@b.com"])
def test_invalid_email_rejected(client, email):
    response = post(client, email=email)
    assert response.status_code == 200
    assert b"valid email" in response.data
    assert all_users() == []


@pytest.mark.parametrize(
    "field", ["name", "email", "password"],
)
def test_empty_field_rejected(client, field):
    values = {"name": "Asha Rao", "email": "asha@example.com", "password": "secret123"}
    values[field] = ""
    response = post(client, **values)
    assert response.status_code == 200
    assert b"All fields are required" in response.data
    assert all_users() == []


def test_whitespace_only_name_rejected(client):
    response = post(client, name="   ")
    assert response.status_code == 200
    assert b"All fields are required" in response.data
    assert all_users() == []


def test_error_keeps_name_and_email_but_not_password(client):
    response = post(client, name="Asha Rao", email="asha@example.com", password="short")
    assert b'value="Asha Rao"' in response.data
    assert b'value="asha@example.com"' in response.data
    assert b"short" not in response.data.replace(b"at least 8 characters", b"")
