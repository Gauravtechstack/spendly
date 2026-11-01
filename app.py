import calendar
import math
import os
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import db_connection, get_db, init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    insert_expense,
)

FILTER_ERROR = "filter_error"  # flash category for the profile date filter
CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
DESCRIPTION_MAX = 200
AMOUNT_MAX = 10_000_000

app = Flask(__name__)
# The fallback is for local development only; set SECRET_KEY in any real deployment.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-key")
# Stops browsers sending the session cookie on cross-site POSTs (basic CSRF mitigation).
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

with app.app_context():
    init_db()
    seed_db()


def login_required(view):
    """Redirect logged-out visitors to the login page (session-based auth)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.template_filter("rupees")
def rupees(value):
    return f"₹{value:,.2f}"


@app.template_filter("nice_date")
def nice_date(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return value


def parse_iso_date(value):
    """Return value normalised to zero-padded YYYY-MM-DD, or None if invalid."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def resolve_date_range(args):
    """Return the validated (date_from, date_to) from query args, or (None, None).

    A filter needs both bounds: a missing or malformed one means "All Time".
    If the range is reversed, flash an error and fall back to "All Time".
    """
    date_from = parse_iso_date(args.get("date_from"))
    date_to = parse_iso_date(args.get("date_to"))
    if not (date_from and date_to):
        return None, None
    if date_from > date_to:
        flash("Start date must be before end date.", FILTER_ERROR)
        return None, None
    return date_from, date_to


def months_ago(today, months):
    """Return the date `months` calendar months before today (day clamped to month end)."""
    # Count months since year 0 so the year wraps correctly across January.
    index = today.year * 12 + (today.month - 1) - months
    year, month = divmod(index, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def build_presets(date_from, date_to, today=None):
    """Quick-select ranges for the profile filter bar, flagging the active one.

    date_from/date_to are the active range (both None for "All Time").
    """
    today = today or date.today()
    ranges = [
        ("This Month", today.replace(day=1).isoformat(), today.isoformat()),
        ("Last 3 Months", months_ago(today, 3).isoformat(), today.isoformat()),
        ("Last 6 Months", months_ago(today, 6).isoformat(), today.isoformat()),
        ("All Time", None, None),
    ]
    return [
        {
            "label": label,
            # "All Time" has no params, so its link is the clean /profile URL.
            "params": {"date_from": start, "date_to": end} if start else {},
            # "All Time" is active when no range is set (None == None).
            "active": start == date_from and end == date_to,
        }
        for label, start, end in ranges
    ]


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def form_error(message):
        return render_template("register.html", error=message, name=name, email=email)

    if not name or not email or not password:
        return form_error("All fields are required.")

    local, _, domain = email.partition("@")
    domain_name, _, tld = domain.rpartition(".")
    if not local or "@" in domain or not domain_name or not tld:
        return form_error("Enter a valid email address.")

    if len(password) < 8:
        return form_error("Password must be at least 8 characters.")

    conn = get_db()
    try:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            return form_error("An account with this email already exists.")
        try:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return form_error("An account with this email already exists.")
    finally:
        conn.close()

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def form_error(message):
        return render_template("login.html", error=message, email=email)

    if not email or not password:
        return form_error("Email and password are required.")

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, name, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return form_error("Invalid email or password.")

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    with db_connection() as conn:
        user = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    date_from, date_to = resolve_date_range(request.args)
    stats = get_summary_stats(user_id, date_from, date_to)
    presets = build_presets(date_from, date_to)

    return render_template(
        "profile.html",
        user=user,
        total=stats["total"],
        count=stats["count"],
        top_category=stats["top_category"],
        expenses=get_recent_transactions(user_id, 10, date_from, date_to),
        breakdown=get_category_breakdown(user_id, date_from, date_to),
        presets=presets,
        custom_active=bool(date_from) and not any(p["active"] for p in presets),
        date_from=date_from or "",
        date_to=date_to or "",
    )


@app.route("/analytics")
@login_required
def analytics():
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    def render_form(error=None, **values):
        values.setdefault("date", date.today().isoformat())
        return render_template(
            "add_expense.html", categories=CATEGORIES, error=error, **values
        )

    if request.method == "GET":
        return render_form()

    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "")
    date_raw = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()
    entered = {
        "amount": amount_raw,
        "category": category,
        "date": date_raw,
        "description": description,
    }

    try:
        amount = float(amount_raw)
    except ValueError:
        amount = None
    if amount is None or not math.isfinite(amount) or not 0 < amount <= AMOUNT_MAX:
        return render_form(
            f"Enter an amount between 0.01 and {AMOUNT_MAX:,}.", **entered
        )

    if category not in CATEGORIES:
        return render_form("Choose a valid category.", **entered)

    expense_date = parse_iso_date(date_raw)
    if expense_date is None:
        return render_form("Enter a valid date.", **entered)

    if len(description) > DESCRIPTION_MAX:
        return render_form(
            f"Description must be {DESCRIPTION_MAX} characters or fewer.", **entered
        )

    try:
        insert_expense(
            session["user_id"],
            round(amount, 2),
            category,
            expense_date,
            description or None,
        )
    except sqlite3.IntegrityError:
        # The session points at a user row that no longer exists.
        session.clear()
        return redirect(url_for("login"))
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
