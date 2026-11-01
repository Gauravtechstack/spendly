# Spec: Delete Expense

## Overview
Step 9 lets a logged-in user permanently remove one of their own expenses. The `/expenses/<id>/delete` route is currently a GET-only placeholder returning a string. This step replaces it with a POST-only handler (a state-changing action must not be reachable by a plain link or prefetch), removes the row, and redirects to the profile page. Each row in the profile transaction table gets a Delete button that asks the user to confirm before submitting. This completes the add / edit / delete expense set.

## Depends on
- Step 1: Database setup (`expenses` table)
- Step 3: Login / Logout (`session["user_id"]`, `login_required`)
- Step 4 / 5: Profile page with the transaction list
- Step 7: Add Expense
- Step 8: Edit Expense (the per-row actions column and the owner-scoped query pattern)

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense and redirect to `/profile` — logged-in only (owner only; 404 if not found or not owned)

The existing GET placeholder is removed: `GET /expenses/<id>/delete` returns 405.

## Database changes
No database changes. The `expenses` table needs no new columns. Deletion is a hard `DELETE`; nothing references `expenses.id`, so no foreign-key handling is required.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — in the per-row `profile-actions` cell, add next to the Edit link a small `<form method="POST" action="{{ url_for('delete_expense', id=expense.id) }}">` with a "Delete" `<button type="submit">` carrying a `data-confirm` attribute (e.g. "Delete this expense? This cannot be undone.").

## Files to change
- `app.py` — replace the placeholder `delete_expense` with a `login_required`, `methods=["POST"]` handler; import `delete_expense` query helper under a non-clashing name (e.g. `delete_expense_row` or `remove_expense`) so it does not shadow the view function.
- `database/queries.py` — add `delete_expense(user_id, expense_id)` (see name note above).
- `templates/profile.html` — add the Delete form/button.
- `static/css/profile.css` — style the Delete button as a link-style danger action using CSS variables (reuse an existing error/danger variable if one exists in `style.css` `:root`; otherwise add one there).
- `static/js/main.js` — small handler: on `submit` of any form with `data-confirm`, call `window.confirm(...)` and cancel the submit if declined. No inline JS in templates.
- `CLAUDE.md` — update the Architecture note: `/expenses/<id>/delete` is implemented (POST-only) and no longer a placeholder.

## Files to create
- `tests/test_delete_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `db_connection()`
- Parameterised queries only
- Passwords hashed with werkzeug (no password handling changes here)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no inline JS handlers (`onclick`, `onsubmit`); behaviour lives in `static/js/main.js`
- Delete is POST-only. Never delete in response to a GET.
- Ownership is enforced in SQL: `DELETE FROM expenses WHERE id = ? AND user_id = ?`. The helper returns whether a row was deleted (`cursor.rowcount > 0`); the route returns 404 when nothing was deleted. Never reveal whether another user's expense exists.
- Keep the view function name `delete_expense` (templates use `url_for`).
- Logged-out POST redirects to `/login` and deletes nothing.
- On success redirect to `url_for("profile")`. Preserve nothing else; no flash message is required.
- The confirmation is a UX aid only; the server must not depend on it.
- Currency, where displayed, uses ₹.

## Definition of done
- [ ] Each row on the profile page shows a Delete button beside Edit
- [ ] Clicking Delete shows a confirmation prompt; cancelling it leaves the expense in place
- [ ] Confirming deletes the expense, redirects to `/profile`, and it no longer appears in the transaction list
- [ ] The summary total, expense count, top category and category breakdown update after a delete
- [ ] Deleting the last expense in a date range shows the empty state
- [ ] `GET /expenses/<id>/delete` returns 405 and deletes nothing
- [ ] POST to `/expenses/<id>/delete` while logged out redirects to `/login` and deletes nothing
- [ ] POST for a non-existent id returns 404
- [ ] POST for another user's expense returns 404 and the expense still exists
- [ ] The Delete button is styled with CSS variables (no hardcoded hex) and looks consistent with the Edit link
- [ ] `pytest tests/test_delete_expense.py` passes
