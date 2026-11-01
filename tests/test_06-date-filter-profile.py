"""Tests for Step 6: date-range filter on GET /profile.

Written from .claude/specs/06-date-filter-profile.md. Query params are
`date_from` and `date_to`; both must be valid and ordered for a filter to apply.
"""
import html as html_lib
import os
import re
import sys
import tempfile
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

# app.py runs init_db()/seed_db() at import time, so point the DB at a throwaway
# file before the first import of app (a no-op if another module imported it first).
import database.db as _dbmod

if "app" not in sys.modules:
    _dbmod.DB_PATH = os.path.join(tempfile.mkdtemp(), "import_time.db")

from app import app, months_ago  # noqa: E402
from database.db import get_db, init_db  # noqa: E402

PASSWORD = "secret123"
FLASH_MSG = "Start date must be before end date."

TODAY = date.today()


def days_ago(n):
    return (TODAY - timedelta(days=n)).isoformat()


# ------------------------------------------------------------------ #
# Fixtures / helpers                                                  #
# ------------------------------------------------------------------ #

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("database.db.DB_PATH", str(tmp_path / "test.db"))
    init_db()
    app.config["TESTING"] = True
    conn = get_db()
    for name, email in (("Asha Rao", "asha@example.com"), ("Ben Cole", "ben@example.com")):
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(PASSWORD)),
        )
    conn.commit()
    conn.close()
    return app.test_client()


def user_id(email):
    conn = get_db()
    try:
        return conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
    finally:
        conn.close()


def login(client, email="asha@example.com"):
    return client.post("/login", data={"email": email, "password": PASSWORD})


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


def get_profile(client, **params):
    response = client.get("/profile", query_string=params)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    return response.data.decode()


def preset_href(page, label):
    """Return the unescaped href of the preset link with the given label."""
    match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>\s*' + re.escape(label), page)
    assert match, f"Preset link '{label}' not found"
    return html_lib.unescape(match.group(1))


@pytest.fixture
def spread(client):
    """Asha's expenses spread over time, well away from window boundaries.

    today        -> this month, last 3m, last 6m
    45 days ago  -> last 3m, last 6m (never in the current month: >31 days)
    135 days ago -> last 6m only (>92 and <181 days)
    300 days ago -> all time only (>184 days)
    """
    uid = user_id("asha@example.com")
    add_expenses([
        (uid, 100.00, "Food", days_ago(0), "Row-today"),
        (uid, 200.50, "Transport", days_ago(45), "Row-45d"),
        (uid, 400.00, "Bills", days_ago(135), "Row-135d"),
        (uid, 1000.00, "Health", days_ago(300), "Row-300d"),
    ])
    login(client)
    return client


@pytest.fixture
def fixed(client):
    """Asha's expenses on fixed dates for custom-range tests."""
    uid = user_id("asha@example.com")
    add_expenses([
        (uid, 10.00, "Food", "2025-01-01", "Fx-jan01"),
        (uid, 20.00, "Food", "2025-01-15", "Fx-jan15"),
        (uid, 30.00, "Transport", "2025-01-31", "Fx-jan31"),
        (uid, 40.00, "Bills", "2025-02-10", "Fx-feb10"),
        (uid, 50.00, "Health", "2025-03-05", "Fx-mar05"),
    ])
    login(client)
    return client


ALL_FIXED = ["Fx-jan01", "Fx-jan15", "Fx-jan31", "Fx-feb10", "Fx-mar05"]


def assert_only(page, present, universe):
    for marker in universe:
        if marker in present:
            assert marker in page, f"Expected {marker} in page"
        else:
            assert marker not in page, f"Did not expect {marker} in page"


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    @pytest.mark.parametrize("params", [
        {},
        {"date_from": "2025-01-01", "date_to": "2025-02-01"},
        {"date_from": "garbage"},
    ])
    def test_profile_with_filter_logged_out_redirects_to_login(self, client, params):
        response = client.get("/profile", query_string=params)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")


# ------------------------------------------------------------------ #
# No params: Step 5 behaviour                                         #
# ------------------------------------------------------------------ #

class TestUnfiltered:
    def test_no_params_shows_all_expenses(self, spread):
        page = get_profile(spread)
        for marker in ("Row-today", "Row-45d", "Row-135d", "Row-300d"):
            assert marker in page, f"{marker} should be visible unfiltered"

    def test_no_params_total_is_sum_of_all(self, spread):
        page = get_profile(spread)
        assert "₹1,700.50" in page, "Total should be sum of all expenses"
        assert 'profile-stat-value">4<' in page, "Transaction count should be 4"

    def test_no_params_no_flash_error(self, spread):
        assert FLASH_MSG not in get_profile(spread)

    def test_no_params_breakdown_includes_all_categories(self, spread):
        page = get_profile(spread)
        for cat in ("Food", "Transport", "Bills", "Health"):
            assert cat in page, f"Category {cat} should appear unfiltered"

    def test_no_params_all_time_preset_is_active(self, spread):
        page = get_profile(spread)
        assert re.search(r'<a[^>]*is-active[^>]*>\s*All Time', page), \
            "All Time preset should be highlighted with no filter"


# ------------------------------------------------------------------ #
# Presets                                                             #
# ------------------------------------------------------------------ #

class TestPresets:
    def test_filter_bar_has_all_four_presets(self, spread):
        page = get_profile(spread)
        for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
            assert label in page, f"Missing preset '{label}'"

    def test_all_time_preset_link_has_no_query_params(self, spread):
        href = preset_href(get_profile(spread), "All Time")
        assert "?" not in href, f"All Time link must be a clean URL, got {href}"
        assert href.rstrip("/").endswith("/profile")

    def test_this_month_preset_link_params(self, spread):
        href = preset_href(get_profile(spread), "This Month")
        assert f"date_from={TODAY.replace(day=1).isoformat()}" in href
        assert f"date_to={TODAY.isoformat()}" in href

    @pytest.mark.parametrize("label", ["Last 3 Months", "Last 6 Months"])
    def test_rolling_presets_end_today(self, spread, label):
        href = preset_href(get_profile(spread), label)
        assert f"date_to={TODAY.isoformat()}" in href
        assert "date_from=" in href

    def test_last_3_months_preset_from_date_roughly_three_months_back(self, spread):
        href = preset_href(get_profile(spread), "Last 3 Months")
        start = re.search(r"date_from=(\d{4}-\d{2}-\d{2})", href).group(1)
        delta = (TODAY - date.fromisoformat(start)).days
        assert 89 <= delta <= 92, f"3-month window should be 89-92 days, got {delta}"

    def test_last_6_months_preset_from_date_roughly_six_months_back(self, spread):
        href = preset_href(get_profile(spread), "Last 6 Months")
        start = re.search(r"date_from=(\d{4}-\d{2}-\d{2})", href).group(1)
        delta = (TODAY - date.fromisoformat(start)).days
        assert 181 <= delta <= 184, f"6-month window should be 181-184 days, got {delta}"

    def test_following_this_month_link_filters_to_current_month(self, spread):
        href = preset_href(get_profile(spread), "This Month")
        page = spread.get(href).data.decode()
        assert "Row-today" in page
        for marker in ("Row-45d", "Row-135d", "Row-300d"):
            assert marker not in page, f"{marker} is outside this month"
        assert "₹100.00" in page
        assert 'profile-stat-value">1<' in page

    def test_following_last_3_months_link_filters_all_sections(self, spread):
        href = preset_href(get_profile(spread), "Last 3 Months")
        page = spread.get(href).data.decode()
        assert_only(page, {"Row-today", "Row-45d"},
                    ["Row-today", "Row-45d", "Row-135d", "Row-300d"])
        assert "₹300.50" in page, "Summary total should respect filter"
        assert 'profile-stat-value">2<' in page
        assert "Bills" not in page and "Health" not in page, \
            "Category breakdown should respect filter"
        assert "Food" in page and "Transport" in page

    def test_following_last_6_months_link_filters_all_sections(self, spread):
        href = preset_href(get_profile(spread), "Last 6 Months")
        page = spread.get(href).data.decode()
        assert_only(page, {"Row-today", "Row-45d", "Row-135d"},
                    ["Row-today", "Row-45d", "Row-135d", "Row-300d"])
        assert "₹700.50" in page
        assert 'profile-stat-value">3<' in page
        assert "Health" not in page

    def test_following_all_time_link_removes_filter(self, spread):
        href = preset_href(get_profile(spread), "All Time")
        page = spread.get(href).data.decode()
        for marker in ("Row-today", "Row-45d", "Row-135d", "Row-300d"):
            assert marker in page
        assert "₹1,700.50" in page

    def test_active_preset_highlighted_for_this_month(self, spread):
        href = preset_href(get_profile(spread), "This Month")
        page = spread.get(href).data.decode()
        assert re.search(r'<a[^>]*is-active[^>]*>\s*This Month', page), \
            "This Month should be highlighted when its range is active"
        assert not re.search(r'<a[^>]*is-active[^>]*>\s*All Time', page), \
            "All Time should not be highlighted when a filter is active"


# ------------------------------------------------------------------ #
# Custom range                                                        #
# ------------------------------------------------------------------ #

class TestCustomRange:
    def test_valid_range_shows_only_expenses_inside(self, fixed):
        page = get_profile(fixed, date_from="2025-01-10", date_to="2025-02-15")
        assert_only(page, {"Fx-jan15", "Fx-jan31", "Fx-feb10"}, ALL_FIXED)

    def test_valid_range_summary_stats_respect_filter(self, fixed):
        page = get_profile(fixed, date_from="2025-01-10", date_to="2025-02-15")
        assert "₹90.00" in page, "Total should be 20+30+40"
        assert 'profile-stat-value">3<' in page

    def test_valid_range_category_breakdown_respects_filter(self, fixed):
        page = get_profile(fixed, date_from="2025-02-01", date_to="2025-02-28")
        assert "Bills" in page
        for cat in ("Food", "Transport", "Health"):
            assert cat not in page, f"{cat} has no expenses in range"

    def test_range_bounds_are_inclusive(self, fixed):
        page = get_profile(fixed, date_from="2025-01-01", date_to="2025-01-31")
        assert_only(page, {"Fx-jan01", "Fx-jan15", "Fx-jan31"}, ALL_FIXED)

    def test_single_day_range_from_equals_to_is_valid(self, fixed):
        page = get_profile(fixed, date_from="2025-01-15", date_to="2025-01-15")
        assert_only(page, {"Fx-jan15"}, ALL_FIXED)
        assert FLASH_MSG not in page

    def test_range_covering_everything_matches_unfiltered(self, fixed):
        page = get_profile(fixed, date_from="2000-01-01", date_to="2999-12-31")
        assert_only(page, set(ALL_FIXED), ALL_FIXED)
        assert "₹150.00" in page

    def test_custom_fields_reflect_active_range(self, fixed):
        page = get_profile(fixed, date_from="2025-01-10", date_to="2025-02-15")
        assert 'type="date"' in page
        assert 'name="date_from"' in page and 'name="date_to"' in page
        assert 'value="2025-01-10"' in page
        assert 'value="2025-02-15"' in page

    def test_apply_button_present(self, fixed):
        assert "Apply" in get_profile(fixed)

    def test_custom_range_does_not_highlight_any_preset(self, fixed):
        page = get_profile(fixed, date_from="2025-01-10", date_to="2025-02-15")
        for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
            assert not re.search(r'<a[^>]*is-active[^>]*>\s*' + label, page), \
                f"{label} should not be active for a custom range"

    def test_recent_list_still_capped_at_ten_when_filtered(self, client):
        uid = user_id("asha@example.com")
        add_expenses([
            (uid, 1.0 + i, "Food", f"2025-04-{i + 1:02d}", f"Cap-{i:02d}")
            for i in range(12)
        ])
        login(client)
        page = get_profile(client, date_from="2025-04-01", date_to="2025-04-30")
        shown = [i for i in range(12) if f"Cap-{i:02d}" in page]
        assert len(shown) == 10, f"Expected 10 transactions, saw {len(shown)}"
        assert shown == list(range(2, 12)), "Most recent 10 should be shown"

    def test_filtered_transactions_ordered_newest_first(self, fixed):
        page = get_profile(fixed, date_from="2025-01-01", date_to="2025-03-31")
        assert page.index("Fx-mar05") < page.index("Fx-feb10") < page.index("Fx-jan01")


# ------------------------------------------------------------------ #
# Invalid input                                                       #
# ------------------------------------------------------------------ #

class TestInvalidInput:
    def test_from_after_to_falls_back_to_unfiltered(self, fixed):
        page = get_profile(fixed, date_from="2025-03-01", date_to="2025-01-01")
        assert_only(page, set(ALL_FIXED), ALL_FIXED)
        assert "₹150.00" in page

    def test_from_after_to_shows_flash_error(self, fixed):
        page = get_profile(fixed, date_from="2025-03-01", date_to="2025-01-01")
        assert FLASH_MSG in page, "Expected user-visible error message"

    def test_from_after_to_does_not_echo_discarded_range_in_inputs(self, fixed):
        page = get_profile(fixed, date_from="2025-03-01", date_to="2025-01-01")
        assert 'value="2025-03-01"' not in page, "Invalid range should be discarded"

    @pytest.mark.parametrize("bad", [
        "not-a-date", "2025-13-01", "2025-02-30", "01-02-2025", "2025/01/01", "20250101",
    ])
    def test_malformed_date_from_falls_back_silently(self, fixed, bad):
        page = get_profile(fixed, date_from=bad, date_to="2025-01-31")
        assert_only(page, set(ALL_FIXED), ALL_FIXED)
        assert FLASH_MSG not in page, "Malformed input is silent, no flash"

    @pytest.mark.parametrize("bad", ["not-a-date", "2025-13-01", "2025-02-30", "tomorrow"])
    def test_malformed_date_to_falls_back_silently(self, fixed, bad):
        page = get_profile(fixed, date_from="2025-01-01", date_to=bad)
        assert_only(page, set(ALL_FIXED), ALL_FIXED)

    def test_both_malformed_falls_back_to_unfiltered(self, fixed):
        page = get_profile(fixed, date_from="abc", date_to="xyz")
        assert_only(page, set(ALL_FIXED), ALL_FIXED)

    @pytest.mark.parametrize("params", [
        {"date_from": "", "date_to": ""},
        {"date_from": "", "date_to": "2025-01-31"},
        {"date_from": "2025-01-01", "date_to": ""},
    ])
    def test_empty_strings_treated_as_absent(self, fixed, params):
        page = get_profile(fixed, **params)
        assert_only(page, set(ALL_FIXED), ALL_FIXED)

    @pytest.mark.parametrize("params", [
        {"date_from": "2025-02-01"},
        {"date_to": "2025-01-10"},
    ])
    def test_only_one_bound_falls_back_to_unfiltered(self, fixed, params):
        page = get_profile(fixed, **params)
        assert_only(page, set(ALL_FIXED), ALL_FIXED)

    @pytest.mark.parametrize("payload", [
        "2025-01-01'; DROP TABLE expenses;--",
        "' OR '1'='1",
        "2025-01-01' OR '1'='1",
    ])
    def test_sql_injection_in_dates_is_harmless(self, fixed, payload):
        response = fixed.get("/profile", query_string={"date_from": payload, "date_to": payload})
        assert response.status_code == 200
        conn = get_db()
        try:
            count = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
        finally:
            conn.close()
        assert count == 5, "expenses table must be intact after injection attempt"

    def test_very_long_date_string_does_not_crash(self, fixed):
        response = fixed.get("/profile", query_string={"date_from": "9" * 5000, "date_to": "1" * 5000})
        assert response.status_code == 200

    def test_repeated_params_do_not_crash(self, fixed):
        response = fixed.get("/profile?date_from=2025-01-01&date_from=bad&date_to=2025-01-31")
        assert response.status_code == 200


# ------------------------------------------------------------------ #
# Empty results                                                       #
# ------------------------------------------------------------------ #

class TestEmptyRange:
    def test_range_with_no_expenses_shows_zero_state(self, fixed):
        page = get_profile(fixed, date_from="2024-01-01", date_to="2024-01-31")
        assert "₹0.00" in page, "Total spent should be ₹0.00"
        assert 'profile-stat-value">0<' in page, "Transaction count should be 0"
        for marker in ALL_FIXED:
            assert marker not in page
        for cat in ("Food", "Transport", "Bills", "Health"):
            assert cat not in page, "Category breakdown should be empty"

    def test_user_with_no_expenses_at_all_filtered_no_error(self, client):
        login(client)
        page = get_profile(client, date_from="2025-01-01", date_to="2025-12-31")
        assert "₹0.00" in page

    def test_this_month_preset_with_no_current_month_expenses(self, client):
        uid = user_id("asha@example.com")
        add_expenses([(uid, 5.0, "Food", days_ago(300), "Old-only")])
        login(client)
        href = preset_href(get_profile(client), "This Month")
        page = client.get(href).data.decode()
        assert "Old-only" not in page
        assert "₹0.00" in page


# ------------------------------------------------------------------ #
# Currency symbol                                                     #
# ------------------------------------------------------------------ #

class TestRupeeSymbol:
    @pytest.mark.parametrize("params", [
        {},
        {"date_from": "2025-01-01", "date_to": "2025-01-31"},
        {"date_from": "2024-01-01", "date_to": "2024-01-02"},
        {"date_from": "bad"},
    ])
    def test_rupee_symbol_shown_regardless_of_filter(self, fixed, params):
        page = get_profile(fixed, **params)
        assert "₹" in page


# ------------------------------------------------------------------ #
# User isolation                                                      #
# ------------------------------------------------------------------ #

class TestUserIsolation:
    @pytest.fixture
    def two_users(self, client):
        asha, ben = user_id("asha@example.com"), user_id("ben@example.com")
        add_expenses([
            (asha, 10.00, "Food", "2025-01-15", "Asha-private"),
            (ben, 7777.00, "Shopping", "2025-01-15", "Ben-private"),
            (ben, 8888.00, "Shopping", days_ago(0), "Ben-today"),
        ])
        return client

    @pytest.mark.parametrize("params", [
        {},
        {"date_from": "2025-01-01", "date_to": "2025-01-31"},
        {"date_from": "2000-01-01", "date_to": "2999-12-31"},
        {"date_from": "2025-02-01", "date_to": "2025-01-01"},
        {"date_from": "junk"},
    ])
    def test_filters_never_expose_other_users_expenses(self, two_users, params):
        login(two_users, "asha@example.com")
        page = get_profile(two_users, **params)
        assert "Ben-private" not in page
        assert "Ben-today" not in page
        assert "₹7,777.00" not in page and "₹8,888.00" not in page
        assert "Shopping" not in page, "Other user's category must not leak"

    def test_filtered_total_only_counts_own_expenses(self, two_users):
        login(two_users, "asha@example.com")
        page = get_profile(two_users, date_from="2025-01-01", date_to="2025-01-31")
        assert "Asha-private" in page
        assert "₹10.00" in page
        assert 'profile-stat-value">1<' in page

    def test_this_month_preset_excludes_other_users_today_expense(self, two_users):
        login(two_users, "asha@example.com")
        href = preset_href(get_profile(two_users), "This Month")
        page = two_users.get(href).data.decode()
        assert "Ben-today" not in page
        assert "₹0.00" in page

    def test_other_user_sees_only_own_data_in_same_range(self, two_users):
        login(two_users, "ben@example.com")
        page = get_profile(two_users, date_from="2025-01-01", date_to="2025-01-31")
        assert "Ben-private" in page
        assert "Asha-private" not in page
        assert "Ben-today" not in page, "Outside the range"


# ------------------------------------------------------------------ #
# DB side effects                                                     #
# ------------------------------------------------------------------ #

class TestNoSideEffects:
    def test_filtering_does_not_modify_expenses(self, fixed):
        def snapshot():
            conn = get_db()
            try:
                return [tuple(r) for r in conn.execute(
                    "SELECT id, user_id, amount, category, date, description "
                    "FROM expenses ORDER BY id").fetchall()]
            finally:
                conn.close()

        before = snapshot()
        get_profile(fixed, date_from="2025-01-10", date_to="2025-02-15")
        get_profile(fixed, date_from="2025-03-01", date_to="2025-01-01")
        get_profile(fixed, date_from="bad")
        assert snapshot() == before, "GET /profile filters must be read-only"


# ------------------------------------------------------------------ #
# months_ago (preset date arithmetic)                                 #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("today,n,expected", [
    (date(2025, 3, 31), 1, date(2025, 2, 28)),   # clamp to shorter month
    (date(2024, 3, 31), 1, date(2024, 2, 29)),   # leap year
    (date(2025, 1, 15), 3, date(2024, 10, 15)),  # wraps across January
    (date(2024, 8, 31), 6, date(2024, 2, 29)),
    (date(2026, 8, 31), 6, date(2026, 2, 28)),
    (date(2025, 12, 5), 6, date(2025, 6, 5)),
])
def test_months_ago(today, n, expected):
    assert months_ago(today, n) == expected
