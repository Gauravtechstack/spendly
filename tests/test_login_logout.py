import pytest
from werkzeug.security import generate_password_hash

from app import app
from database.db import get_db, init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("database.db.DB_PATH", str(tmp_path / "test.db"))
    init_db()
    app.config["TESTING"] = True
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Asha Rao", "asha@example.com", generate_password_hash("secret123")),
    )
    conn.commit()
    conn.close()
    return app.test_client()


def login(client, email="asha@example.com", password="secret123"):
    return client.post("/login", data={"email": email, "password": password})


def session_data(client):
    with client.session_transaction() as sess:
        return dict(sess)


def test_get_login_renders_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Welcome back" in response.data


def test_valid_login_redirects_to_profile_and_sets_session(client):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    data = session_data(client)
    assert data["user_id"] == 1
    assert data["user_name"] == "Asha Rao"


def test_session_does_not_hold_password_or_hash(client):
    login(client)
    data = session_data(client)
    assert set(data) == {"user_id", "user_name"}
    assert "secret123" not in str(data)
    assert "pbkdf2" not in str(data) and "scrypt" not in str(data)


def test_email_is_case_and_whitespace_insensitive(client):
    response = login(client, email="  Asha@Example.COM ")
    assert response.status_code == 302
    assert session_data(client)["user_id"] == 1


@pytest.mark.parametrize(
    "email, password",
    [("asha@example.com", "wrongpass1"), ("nobody@example.com", "secret123")],
)
def test_bad_credentials_show_generic_error(client, email, password):
    response = login(client, email=email, password=password)
    assert response.status_code == 200
    assert b"Invalid email or password." in response.data
    assert "user_id" not in session_data(client)


@pytest.mark.parametrize("field", ["email", "password"])
def test_empty_field_rejected(client, field):
    values = {"email": "asha@example.com", "password": "secret123"}
    values[field] = ""
    response = login(client, **values)
    assert response.status_code == 200
    assert b"Email and password are required." in response.data
    assert "user_id" not in session_data(client)


def test_failed_login_keeps_email_but_not_password(client):
    response = login(client, password="wrongpass1")
    assert b'value="asha@example.com"' in response.data
    assert b"wrongpass1" not in response.data


def test_login_page_redirects_when_logged_in(client):
    login(client)
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_navbar_reflects_login_state(client):
    before = client.get("/").data
    assert b"Sign in" in before and b"Get started" in before
    assert b"Sign out" not in before

    login(client)
    after = client.get("/").data
    assert b"Sign out" in after
    assert b"Get started" not in after


def test_logout_clears_session_and_redirects_home(client):
    login(client)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert "user_id" not in session_data(client)
    assert client.get("/login").status_code == 200
