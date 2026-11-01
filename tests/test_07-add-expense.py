import re

import pytest
from werkzeug.security import generate_password_hash

from app import app
from database.db import get_db, init_db
from database.queries import insert_expense

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
ERROR_PATTERN = re.compile(r"error|invalid|required|must|valid|please", re.IGNORECASE)

VALID = {
    "amount": "50.0",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}


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


@pytest.fixture
def auth_client(client):
    login(client)
    return client


def fetch_expenses(user_id=None):
    conn = get_db()
    if user_id is None:
        rows = conn.execute("SELECT * FROM expenses").fetchall()
    else:
        rows = conn.execute("SELECT * FROM expenses WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return rows


def user_id_for(email):
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"]


def post_expense(client, **overrides):
    data = dict(VALID)
    data.update(overrides)
    # Allow removing a field by passing None
    data = {k: v for k, v in data.items() if v is not None}
    return client.post("/expenses/add", data=data)


# ---------------------------------------------------------------- unit tests

class TestInsertExpense:
    def test_insert_expense_valid_row_is_stored(self, client):
        uid = user_id_for("asha@example.com")
        insert_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        rows = fetch_expenses(uid)
        assert len(rows) == 1, "Expected exactly one inserted row"
        row = rows[0]
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"
        assert row["user_id"] == uid

    def test_insert_expense_none_description_stored_as_null(self, client):
        uid = user_id_for("asha@example.com")
        insert_expense(uid, 12.5, "Bills", "2026-03-21", None)
        rows = fetch_expenses(uid)
        assert len(rows) == 1
        assert rows[0]["description"] is None, "Description should be NULL"

    def test_insert_expense_sql_injection_text_is_stored_literally(self, client):
        uid = user_id_for("asha@example.com")
        evil = "x'); DROP TABLE expenses; --"
        insert_expense(uid, 1.0, "Other", "2026-03-22", evil)
        rows = fetch_expenses(uid)
        assert len(rows) == 1
        assert rows[0]["description"] == evil


# ---------------------------------------------------------------- auth guard

class TestAuthGuard:
    def test_get_add_expense_logged_out_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_post_add_expense_logged_out_redirects_to_login(self, client):
        response = post_expense(client)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_post_add_expense_logged_out_saves_nothing(self, client):
        post_expense(client)
        assert fetch_expenses() == [], "No expense may be saved when logged out"


# ---------------------------------------------------------------- GET form

class TestAddExpenseForm:
    def test_get_logged_in_returns_200(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200

    def test_get_contains_post_form(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        form_tags = re.findall(r"<form[^>]*>", html, re.IGNORECASE)
        assert any(
            re.search(r'method\s*=\s*["\']post["\']', tag, re.IGNORECASE) for tag in form_tags
        ), "Expected a <form> with method POST"

    @pytest.mark.parametrize("field", ["amount", "category", "date", "description"])
    def test_get_contains_all_fields(self, auth_client, field):
        html = auth_client.get("/expenses/add").data.decode()
        assert re.search(rf'name\s*=\s*["\']{field}["\']', html), f"Missing field {field}"

    def test_get_category_select_has_exactly_seven_categories(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        match = re.search(
            r'<select[^>]*name\s*=\s*["\']category["\'][^>]*>(.*?)</select>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        assert match, "Expected a <select name='category'>"
        options = re.findall(r"<option[^>]*>(.*?)</option>", match.group(1), re.DOTALL)
        options = [o.strip() for o in options]
        assert sorted(options) == sorted(CATEGORIES), f"Unexpected options: {options}"

    def test_get_date_input_defaults_to_today(self, auth_client):
        from datetime import date

        html = auth_client.get("/expenses/add").data.decode()
        assert date.today().isoformat() in html, "Date should default to today"

    def test_get_has_save_button_and_cancel_link_to_profile(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        assert "Save Expense" in html
        assert 'href="/profile"' in html


# ---------------------------------------------------------------- POST valid

class TestAddExpenseSuccess:
    def test_post_valid_redirects_to_profile(self, auth_client):
        response = post_expense(auth_client)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

    def test_post_valid_saves_row_for_session_user(self, auth_client):
        post_expense(auth_client)
        uid = user_id_for("asha@example.com")
        rows = fetch_expenses(uid)
        assert len(rows) == 1
        row = rows[0]
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_post_valid_does_not_save_under_other_user(self, auth_client):
        post_expense(auth_client)
        assert fetch_expenses(user_id_for("ben@example.com")) == []

    def test_post_valid_ignores_spoofed_user_id_field(self, auth_client):
        ben = user_id_for("ben@example.com")
        auth_client.post("/expenses/add", data={**VALID, "user_id": str(ben)})
        assert fetch_expenses(ben) == [], "Client-supplied user_id must be ignored"
        assert len(fetch_expenses(user_id_for("asha@example.com"))) == 1

    def test_post_valid_expense_appears_on_profile(self, auth_client):
        post_expense(auth_client, description="UniqueLunchMarker")
        html = auth_client.get("/profile").data.decode()
        assert "UniqueLunchMarker" in html

    def test_post_valid_follow_redirect_lands_on_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data=VALID, follow_redirects=True)
        assert response.status_code == 200
        assert b"asha@example.com" in response.data

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_post_each_valid_category_accepted(self, auth_client, category):
        response = post_expense(auth_client, category=category)
        assert response.status_code == 302
        assert fetch_expenses()[0]["category"] == category

    def test_post_decimal_amount_saved_accurately(self, auth_client):
        post_expense(auth_client, amount="199.99")
        assert fetch_expenses()[0]["amount"] == pytest.approx(199.99)

    def test_post_sql_injection_description_stored_literally(self, auth_client):
        evil = "'; DROP TABLE expenses; --"
        response = post_expense(auth_client, description=evil)
        assert response.status_code == 302
        rows = fetch_expenses()
        assert len(rows) == 1
        assert rows[0]["description"] == evil


# ---------------------------------------------------------------- description

class TestOptionalDescription:
    def test_post_missing_description_redirects_and_stores_null(self, auth_client):
        response = post_expense(auth_client, description=None)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")
        rows = fetch_expenses()
        assert len(rows) == 1
        assert rows[0]["description"] is None

    @pytest.mark.parametrize("blank", ["", "   ", "\t "])
    def test_post_blank_description_stored_as_null(self, auth_client, blank):
        response = post_expense(auth_client, description=blank)
        assert response.status_code == 302
        assert fetch_expenses()[0]["description"] is None

    def test_post_description_is_stripped(self, auth_client):
        post_expense(auth_client, description="  Lunch  ")
        assert fetch_expenses()[0]["description"] == "Lunch"


# ---------------------------------------------------------------- validation

class TestValidationErrors:
    def assert_rerendered_with_error(self, response):
        assert response.status_code == 200, "Form should be re-rendered with 200"
        html = response.data.decode()
        assert "<form" in html, "Form should be shown again"
        assert ERROR_PATTERN.search(html), "Expected an error message in the response"
        assert fetch_expenses() == [], "Nothing should be saved on validation error"

    def test_post_missing_amount_shows_error(self, auth_client):
        self.assert_rerendered_with_error(post_expense(auth_client, amount=None))

    @pytest.mark.parametrize("amount", ["", "   "])
    def test_post_blank_amount_shows_error(self, auth_client, amount):
        self.assert_rerendered_with_error(post_expense(auth_client, amount=amount))

    @pytest.mark.parametrize("amount", ["0", "0.0", "0.00"])
    def test_post_zero_amount_shows_error(self, auth_client, amount):
        self.assert_rerendered_with_error(post_expense(auth_client, amount=amount))

    @pytest.mark.parametrize("amount", ["-1", "-50.5", "-0.01"])
    def test_post_negative_amount_shows_error(self, auth_client, amount):
        self.assert_rerendered_with_error(post_expense(auth_client, amount=amount))

    @pytest.mark.parametrize("amount", ["abc", "12abc", "1,000x", "$$"])
    def test_post_non_numeric_amount_shows_error(self, auth_client, amount):
        self.assert_rerendered_with_error(post_expense(auth_client, amount=amount))

    @pytest.mark.parametrize("category", ["Groceries", "food", "", "Food; DROP TABLE expenses"])
    def test_post_invalid_category_shows_error(self, auth_client, category):
        self.assert_rerendered_with_error(post_expense(auth_client, category=category))

    def test_post_missing_category_shows_error(self, auth_client):
        self.assert_rerendered_with_error(post_expense(auth_client, category=None))

    @pytest.mark.parametrize(
        "bad_date",
        ["not-a-date", "2026-13-01", "2026-02-30", "20-03-2026", "2026/03/20", ""],
    )
    def test_post_invalid_date_shows_error(self, auth_client, bad_date):
        self.assert_rerendered_with_error(post_expense(auth_client, date=bad_date))

    def test_post_missing_date_shows_error(self, auth_client):
        self.assert_rerendered_with_error(post_expense(auth_client, date=None))

    def test_post_error_preserves_submitted_values(self, auth_client):
        response = post_expense(
            auth_client, amount="0", description="KeepMeDescription", date="2026-04-15"
        )
        assert response.status_code == 200
        html = response.data.decode()
        assert "KeepMeDescription" in html, "Description should be re-populated"
        assert "2026-04-15" in html, "Date should be re-populated"

    def test_post_error_preserves_amount_value(self, auth_client):
        response = post_expense(auth_client, amount="abc", description="x")
        html = response.data.decode()
        assert response.status_code == 200
        assert "abc" in html, "Previously entered amount should be retained"

    def test_post_error_preserves_selected_category(self, auth_client):
        response = post_expense(auth_client, amount="0", category="Health")
        html = response.data.decode()
        match = re.search(
            r"<option[^>]*>\s*Health\s*</option>", html, re.IGNORECASE
        )
        assert match, "Health option should be present"
        assert "selected" in match.group(0).lower(), "Health should remain selected"

    def test_post_error_does_not_leak_into_other_users_data(self, auth_client):
        post_expense(auth_client, amount="-5")
        assert fetch_expenses(user_id_for("ben@example.com")) == []

    def test_post_description_html_is_escaped_on_rerender(self, auth_client):
        response = post_expense(auth_client, amount="0", description="<script>alert(1)</script>")
        assert b"<script>alert(1)</script>" not in response.data, "Output must be escaped"


# ---------------------------------------------------------------- navigation

class TestNavigation:
    def test_navbar_hides_add_expense_when_logged_out(self, client):
        html = client.get("/terms").data.decode()
        assert "Add Expense" not in html
        assert "/expenses/add" not in html

    def test_navbar_shows_add_expense_when_logged_in(self, auth_client):
        html = auth_client.get("/terms").data.decode()
        assert "Add Expense" in html
        assert 'href="/expenses/add"' in html

    def test_navbar_add_expense_link_gone_after_logout(self, auth_client):
        auth_client.get("/logout")
        html = auth_client.get("/terms").data.decode()
        assert "Add Expense" not in html

    def test_profile_page_has_add_expense_link(self, auth_client):
        html = auth_client.get("/profile").data.decode()
        assert 'href="/expenses/add"' in html
        assert "Add Expense" in html

    def test_add_expense_page_uses_rupee_not_other_currency(self, auth_client):
        html = auth_client.get("/expenses/add").data.decode()
        assert "£" not in html
        assert "$" not in html


# ---------------------------------------------------------------- review follow-ups

class TestReviewFollowUps:
    def test_amount_above_maximum_is_rejected(self, auth_client):
        response = post_expense(auth_client, amount="10000000.01")
        assert response.status_code == 200
        assert fetch_expenses() == []

    def test_huge_float_amount_is_rejected(self, auth_client):
        response = post_expense(auth_client, amount="1e308")
        assert response.status_code == 200
        assert fetch_expenses() == []

    def test_amount_at_maximum_is_accepted(self, auth_client):
        response = post_expense(auth_client, amount="10000000")
        assert response.status_code == 302
        assert len(fetch_expenses()) == 1

    def test_deleted_user_session_redirects_to_login(self, auth_client):
        conn = get_db()
        conn.execute("DELETE FROM users WHERE email = ?", ("asha@example.com",))
        conn.commit()
        conn.close()
        response = post_expense(auth_client)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        assert fetch_expenses() == []

    def test_session_cookie_is_samesite_lax(self, client):
        response = login(client)
        cookies = response.headers.getlist("Set-Cookie")
        assert any("SameSite=Lax" in c for c in cookies)
