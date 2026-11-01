import pytest
from werkzeug.security import generate_password_hash

from app import app
from database.db import get_db, init_db
from database.queries import insert_expense, remove_expense


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


def user_id_for(email):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"]


def exists(expense_id):
    conn = get_db()
    row = conn.execute("SELECT 1 FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    conn.close()
    return row is not None


@pytest.fixture
def expense_id(client):
    return insert_expense(
        user_id_for("asha@example.com"), 50.0, "Food", "2026-03-20", "Unique lunch"
    )


@pytest.fixture
def other_expense_id(client):
    return insert_expense(
        user_id_for("asha@example.com"), 20.0, "Bills", "2026-03-21", "Keep me"
    )


# ---------------------------------------------------------------- unit tests

class TestRemoveExpense:
    def test_deletes_own_row(self, client, expense_id):
        assert remove_expense(user_id_for("asha@example.com"), expense_id) is True
        assert not exists(expense_id)

    def test_other_users_row_not_deleted(self, client, expense_id):
        assert remove_expense(user_id_for("ben@example.com"), expense_id) is False
        assert exists(expense_id)

    def test_missing_id_returns_false(self, client):
        assert remove_expense(user_id_for("asha@example.com"), 9999) is False


# --------------------------------------------------------------- route tests

class TestDeleteRoute:
    def test_logged_out_post_redirects_and_keeps_row(self, client, expense_id):
        resp = client.post(f"/expenses/{expense_id}/delete")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]
        assert exists(expense_id)

    def test_get_not_allowed_and_keeps_row(self, client, expense_id):
        login(client)
        assert client.get(f"/expenses/{expense_id}/delete").status_code == 405
        assert exists(expense_id)

    def test_owner_delete_redirects_to_profile(self, client, expense_id, other_expense_id):
        login(client)
        resp = client.post(f"/expenses/{expense_id}/delete")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")
        assert not exists(expense_id)
        assert exists(other_expense_id)

    def test_missing_id_404(self, client):
        login(client)
        assert client.post("/expenses/9999/delete").status_code == 404

    def test_other_users_expense_404_and_kept(self, client, expense_id):
        login(client, "ben@example.com")
        assert client.post(f"/expenses/{expense_id}/delete").status_code == 404
        assert exists(expense_id)


class TestProfile:
    def test_row_has_post_delete_form_with_confirm(self, client, expense_id):
        login(client)
        body = client.get("/profile").get_data(as_text=True)
        assert f'action="/expenses/{expense_id}/delete"' in body
        assert 'method="POST"' in body
        assert "data-confirm=" in body

    def test_deleted_expense_disappears_from_profile(self, client, expense_id, other_expense_id):
        login(client)
        client.post(f"/expenses/{expense_id}/delete")
        body = client.get("/profile").get_data(as_text=True)
        assert "Unique lunch" not in body
        assert "Keep me" in body
