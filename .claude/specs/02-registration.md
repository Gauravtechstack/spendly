# Spec: Registration

## Overview
Make the existing registration form functional. Today `GET /register` renders `register.html`, but the form's `POST` returns 405 because the route only accepts GET. This step lets a visitor create a Spendly account: the submitted name, email and password are validated, the password is hashed, a row is inserted into `users`, and the visitor is redirected to the login page. It is the first write path in the app and unblocks login/logout (Step 3), which needs real user accounts to authenticate against. Registration does not start a session; sessions arrive with login.

## Depends on
- Step 01 — Database setup (`users` table with `UNIQUE` email, `get_db()`, `init_db()`).

## Routes
- `GET /register` — render the empty registration form — public (existing, unchanged)
- `POST /register` — validate input, create the user, redirect to `/login` on success; re-render the form with an error on failure — public

Implemented by adding `methods=["GET", "POST"]` to the existing `register` view in `app.py`; no new view functions.

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email UNIQUE NOT NULL`, `password_hash`, `created_at`) already covers everything needed. Duplicate emails are rejected by checking for an existing row and by catching `sqlite3.IntegrityError` from the `UNIQUE` constraint.

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html` — repopulate `name` and `email` inputs with the submitted values after a validation error (never the password); change `action="/register"` to `action="{{ url_for('register') }}"`. The existing `{% if error %}` block is reused for error messages.

## Files to change
- `app.py` — import `request`, `redirect`, `url_for`; import `sqlite3` and `generate_password_hash`; accept GET and POST on `/register` and implement the POST handler.
- `templates/register.html` — see above.

## Files to create
- `tests/test_registration.py` — pytest tests for the registration route (uses a temporary database, not `spendly.db`).

## New dependencies
No new dependencies (`werkzeug` and `pytest`/`pytest-flask` are already installed).

## Rules for implementation
- No SQLAlchemy or ORMs — plain `sqlite3` via `get_db()`
- Parameterised queries only — never build SQL with string formatting or f-strings
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log the plain password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Replace the existing `register` view in place; do not add a new route or rename the view function (templates use `url_for('register')`)
- Strip whitespace from `name` and `email`; lowercase `email` before checking and storing it
- Validation, each failing with a clear message in `error` and HTTP 200 re-render of the form:
  - name, email and password are all required
  - email must contain a single `@` with text on both sides and a `.` in the domain
  - password must be at least 8 characters (matches the form placeholder)
  - email must not already be registered
- Always close the DB connection in a `finally` block, as `database/db.py` does
- Do not introduce sessions, `secret_key` or flash messages in this step; they belong to Step 3
- On success, redirect with `redirect(url_for("login"))`

## Definition of done
- [ ] `venv/Scripts/python app.py` starts without errors
- [ ] `GET /register` still renders the form (200)
- [ ] Submitting the form with valid new details redirects to `/login` (302) instead of returning 405
- [ ] After a successful registration, a new row exists in `users` with the entered name and lowercased email
- [ ] The stored `password_hash` is a werkzeug hash and does not equal the entered password
- [ ] Registering `demo@spendly.com` shows an "already registered" style error and creates no second row
- [ ] Registering the same email in different case (e.g. `Demo@Spendly.com`) is also rejected
- [ ] A password shorter than 8 characters shows an error and creates no row
- [ ] An invalid email (e.g. `foo`, `foo@`) shows an error and creates no row
- [ ] Empty name, email or password shows an error and creates no row (also when bypassing the browser's `required` attribute)
- [ ] After any validation error, the name and email fields keep their submitted values and the password field is empty
- [ ] Error messages appear in the existing `.auth-error` box
- [ ] `venv/Scripts/python -m pytest` passes, including the new registration tests
