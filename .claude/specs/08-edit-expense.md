# Spec: Edit Expense

## Overview
Step 8 lets a logged-in user change an existing expense. The route `/expenses/<id>/edit` is currently a GET-only placeholder returning a string; this step replaces it with a GET + POST handler that shows a form pre-filled with the expense's current values, validates the submission with the same rules as Add Expense, updates the row, and redirects to the profile page. Users may only edit their own expenses. An "Edit" link is added to each row of the transaction table on the profile page so the feature is reachable.

## Depends on
- Step 1: Database setup (`expenses` table)
- Step 3: Login / Logout (`session["user_id"]`, `login_required`)
- Step 4 / 5: Profile page with the transaction list
- Step 7: Add Expense (validation rules, `CATEGORIES`, `add_expense.html` form layout)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the expense — logged-in only (owner only; 404 if not found or not owned)
- `POST /expenses/<int:id>/edit` — validate and update the expense, redirect to `/profile` — logged-in only (owner only; 404 if not found or not owned)

## Database changes
No database changes. The existing `expenses` table (`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`) is sufficient.

## Templates
- **Create:** `templates/edit_expense.html` — extends `base.html`; form with `method="POST"` posting to `url_for('edit_expense', id=expense_id)`; fields `amount`, `category` (select of the 7 categories), `date`, `description` pre-filled; "Save Changes" button and a cancel link to `/profile`; shows the validation error and re-populates submitted values on failure.
  - Preferred: reuse the markup/styles of `add_expense.html`. If it is cleaner, extract shared form markup into an included partial rather than duplicating it.
- **Modify:** `templates/profile.html` — add an "Edit" link per row in the transactions table pointing to `url_for('edit_expense', id=expense.id)`.

## Files to change
- `app.py` — replace the placeholder `edit_expense` with a `login_required` GET + POST handler; import `get_expense` and `update_expense`; factor the amount/category/date/description validation out of `add_expense` into a shared helper so both routes use identical rules.
- `database/queries.py` — add `get_expense(user_id, expense_id)` and `update_expense(user_id, expense_id, amount, category, date, description)`.
- `templates/profile.html` — add Edit link per row.
- `static/css/style.css` (or the existing profile styles) — style the Edit link using CSS variables, if needed.

## Files to create
- `templates/edit_expense.html`
- `tests/test_edit_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `db_connection()`
- Parameterised queries only
- Passwords hashed with werkzeug (no password handling changes here)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles; currency always displays as ₹
- Ownership is enforced in SQL: both `get_expense` and `update_expense` filter on `id = ? AND user_id = ?`. `update_expense` returns whether a row was changed; the route returns 404 when no row matches. Never reveal whether another user's expense exists.
- Keep the route function name `edit_expense` (templates use `url_for`).
- Validation is identical to Add Expense: amount finite and in (0, `AMOUNT_MAX`], rounded to 2 decimals; category in `CATEGORIES`; date valid `YYYY-MM-DD` via `parse_iso_date`; description stripped, max `DESCRIPTION_MAX`, stored as `None` if blank.
- On validation error, re-render the form (HTTP 200) with the error and the submitted values.
- On success, redirect to `url_for("profile")`. `user_id` and `created_at` are never modified.
- Logged-out access to GET and POST redirects to `/login`.

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Each row on the profile page has an Edit link that opens that expense's edit form
- [ ] The edit form is pre-filled with the expense's current amount, category, date and description
- [ ] The category dropdown contains exactly the 7 categories, with the current one selected
- [ ] Submitting valid changes redirects to `/profile` and the updated values appear in the transaction list, summary total and category breakdown
- [ ] Clearing the description saves successfully and the row shows "—"
- [ ] Zero, negative, non-numeric or missing amount re-renders the form with an error and the entered values kept
- [ ] An invalid category or invalid date re-renders the form with an error
- [ ] Visiting the edit URL for a non-existent id returns 404
- [ ] Visiting or POSTing to the edit URL for another user's expense returns 404 and does not change that expense
- [ ] The Cancel link returns to `/profile` without changing anything
- [ ] `pytest tests/test_edit_expense.py` passes
