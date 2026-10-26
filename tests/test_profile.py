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
    for name, email in (("Asha Rao", "asha@example.com"), ("Ben Cole", "ben@example.com")):
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash("secret123")),
        )
    conn.commit()
    conn.close()
    return app.test_client()


def login(client, email="asha@example.com"):
    return client.post("/login", data={"email": email, "password": "secret123"})


def add_expenses(rows):
    """rows: (user_id, amount, category, date, description)"""
    conn = get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_logged_out_redirects_to_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_logged_in_shows_identity(client):
    login(client)
    response = client.get("/profile")
    assert response.status_code == 200
    assert b"Asha Rao" in response.data
    assert b"asha@example.com" in response.data
    assert b"Member since" in response.data


def test_summary_and_ordering(client):
    add_expenses([
        (1, 1000.0, "Food", "2026-01-05", "Older"),
        (1, 2500.5, "Shopping", "2026-02-10", "Newer"),
        (1, 200.0, "Food", "2026-01-20", None),
    ])
    login(client)
    html = client.get("/profile").data.decode()
    assert "₹3,700.50" in html
    assert 'profile-stat-value">3<' in html
    assert 'profile-stat-value">Shopping<' in html
    assert html.index("Newer") < html.index("Older")
    assert "—" in html


def test_recent_list_capped_at_ten(client):
    add_expenses([(1, 1.0, "Food", f"2026-01-{day:02d}", f"item-{day}") for day in range(1, 13)])
    login(client)
    html = client.get("/profile").data.decode()
    assert html.count("<tr>") == 11  # header row + 10 expenses
    assert "item-12" in html
    assert "item-1<" not in html


def test_empty_state(client):
    login(client)
    response = client.get("/profile")
    assert response.status_code == 200
    assert b"No expenses yet" in response.data
    assert "₹0.00".encode() in response.data


def test_other_users_expenses_hidden(client):
    add_expenses([(2, 99.0, "Travel", "2026-01-01", "Bens secret trip")])
    login(client)
    assert b"Bens secret trip" not in client.get("/profile").data


def test_missing_user_clears_session(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 999
        sess["user_name"] = "Ghost"
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_password_hash_not_rendered(client):
    login(client)
    assert b"pbkdf2" not in client.get("/profile").data
    assert b"scrypt" not in client.get("/profile").data


def test_navbar_links(client):
    html = client.get("/").data.decode()
    assert ">Profile<" not in html and ">Sign out<" not in html
    login(client)
    html = client.get("/profile").data.decode()
    assert ">Profile<" in html and ">Sign out<" in html


def test_description_is_escaped(client):
    add_expenses([(1, 5.0, "Other", "2026-01-01", "<script>alert(1)</script>")])
    login(client)
    html = client.get("/profile").data.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("path", ["/", "/login", "/register"])
def test_logged_in_user_is_redirected_to_profile(client, path):
    login(client)
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
