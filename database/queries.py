from database.db import db_connection


def _date_clause(date_from, date_to):
    """Return (sql_fragment, params) restricting expenses.date to an inclusive range.

    The fragment is built only from fixed strings; dates travel as parameters.
    Either bound may be omitted for an open-ended range.
    """
    sql = ""
    params = []
    if date_from:
        sql += " AND date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date <= ?"
        params.append(date_to)
    return sql, tuple(params)


def insert_expense(user_id, amount, category, date, description=None):
    """Insert one expense for the user and return its new row id."""
    with db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cur.lastrowid


def get_expense(user_id, expense_id):
    """Return the user's expense row, or None if it doesn't exist or isn't theirs."""
    with db_connection() as conn:
        return conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()


def update_expense(user_id, expense_id, amount, category, date, description=None):
    """Update the user's expense. Return True if a row was changed, else False."""
    with db_connection() as conn:
        cur = conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
            "WHERE id = ? AND user_id = ?",
            (amount, category, date, description, expense_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return {'total', 'count', 'top_category'} for the user's (filtered) expenses."""
    clause, params = _date_clause(date_from, date_to)
    with db_connection() as conn:
        summary = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
            "FROM expenses WHERE user_id = ?" + clause,
            (user_id, *params),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + clause +
            " GROUP BY category ORDER BY SUM(amount) DESC, category LIMIT 1",
            (user_id, *params),
        ).fetchone()
    return {
        "total": summary["total"],
        "count": summary["count"],
        "top_category": top["category"] if top else None,
    }


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Return up to `limit` of the user's (filtered) expenses, newest first."""
    clause, params = _date_clause(date_from, date_to)
    with db_connection() as conn:
        return conn.execute(
            "SELECT id, date, description, category, amount FROM expenses "
            "WHERE user_id = ?" + clause + " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *params, limit),
        ).fetchall()


def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return a list of {'category', 'total', 'percent'} sorted by total, descending."""
    clause, params = _date_clause(date_from, date_to)
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause +
            " GROUP BY category ORDER BY total DESC, category",
            (user_id, *params),
        ).fetchall()

    grand_total = sum(row["total"] for row in rows)
    if not grand_total:
        return []
    return [
        {
            "category": row["category"],
            "total": row["total"],
            "percent": round(row["total"] / grand_total * 100),
        }
        for row in rows
    ]
