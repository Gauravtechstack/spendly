# Spec: Login and Logout

## Overview
Make the existing sign-in form functional and replace the `/logout` placeholder. Today `GET /login` renders `login.html`, but its `POST` returns 405 because the route only accepts GET, and `/logout` returns the string "Logout — coming in Step 3". This step lets a registered user authenticate with email and password, stores their identity in a Flask session, and lets them sign out again. It introduces the app's first session state (`secret_key`, `session`), which the later logged-in features (profile, add/edit/delete expense) depend on. The navbar also becomes session-aware so signed-in users see "Sign out" instead of "Sign in / Get started".

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`, demo user `demo@spendly.com` / `demo123`).
- Step 02 — Registration (creates real users with werkzeug password hashes and redirects to `/login`).

## Routes
- `GET /login` — render the sign-in form; if already logged in, redirect to `/profile` — public (existing, extended)
- `POST /login` — validate credentials, start a session, redirect to `/profile` on success; re-render the form with an error on failure — public
- `GET /logout` — clear the session and redirect to `/` — logged-in (harmless if not logged in; still redirects to `/`)

Implemented by adding `methods=["GET", "POST"]` to the existing `login` view and replacing the body of the existing `logout` view in `app.py`; no new view functions. `/profile` remains the Step 4 placeholder and is only the redirect target.

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email UNIQUE NOT NULL`, `password_hash`, `created_at`) is sufficient. Login looks up a user by lowercased email and verifies the password with `check_password_hash`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — change `action="/login"` to `action="{{ url_for('login') }}"`; repopulate the `email` input with the submitted value after a failed attempt (never the password). The existing `{% if error %}` block is reused for error messages.
  - `templates/base.html` — in `.nav-links`, show `Sign in` and `Get started` when `session.user_id` is not set, and a `Sign out` link to `url_for('logout')` when it is.

## Files to change
- `app.py` — import `session` and `check_password_hash`; set `app.secret_key`; accept GET and POST on `/login` and implement the POST handler; implement `/logout`.
- `templates/login.html` — see above.
- `templates/base.html` — see above.

## Files to create
- `tests/test_login_logout.py` — pytest tests for login and logout (uses a temporary database, not `spendly.db`, following the approach in `tests/test_registration.py`).

## New dependencies
No new dependencies (`flask` sessions and `werkzeug` are already installed).

## Rules for implementation
- No SQLAlchemy or ORMs — plain `sqlite3` via `get_db()`
- Parameterised queries only — never build SQL with string formatting or f-strings
- Passwords hashed with werkzeug; verify with `check_password_hash`, never compare or log plain passwords
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Replace the existing `login` and `logout` views in place; do not add new routes or rename view functions (templates use `url_for('login')` and `url_for('logout')`)
- `app.secret_key` is read from the `SECRET_KEY` environment variable, with a clearly-labelled development fallback string so the app still starts locally; never commit a real secret
- Strip whitespace from `email` and lowercase it before the lookup
- On success store only `session["user_id"]` (the integer id) and `session["user_name"]`; never store the password hash in the session
- Use one generic error for both unknown email and wrong password ("Invalid email or password.") so account existence is not revealed; empty email or password gives "Email and password are required."
- Failed attempts re-render `login.html` with HTTP 200 and the `error` variable
- On success, call `session.clear()` before setting the user keys to avoid session fixation, then `redirect(url_for("profile"))`
- `/logout` calls `session.clear()` and redirects with `redirect(url_for("landing"))`
- Always close the DB connection in a `finally` block, as `database/db.py` does
- Do not build any other auth features here (no "remember me", password reset, `login_required` decorator or flash messages); protecting other routes belongs to later steps

## Definition of done
- [ ] `venv/Scripts/python app.py` starts without errors
- [ ] `GET /login` still renders the form (200) when logged out
- [ ] Submitting the form with `demo@spendly.com` / `demo123` redirects to `/profile` (302) instead of returning 405
- [ ] Logging in with a newly registered account (from `/register`) works
- [ ] Email is matched case-insensitively and ignores surrounding whitespace (e.g. ` Demo@Spendly.com `)
- [ ] A wrong password shows "Invalid email or password." in the `.auth-error` box and does not log the user in
- [ ] An unknown email shows the same "Invalid email or password." message
- [ ] Empty email or password (also when bypassing the browser's `required` attribute) shows an error and does not log the user in
- [ ] After a failed attempt the email field keeps its submitted value and the password field is empty
- [ ] After a successful login, the navbar shows "Sign out" and no longer shows "Sign in" / "Get started"
- [ ] Visiting `/login` while logged in redirects to `/profile`
- [ ] `GET /logout` clears the session, redirects to `/` (302), and the navbar shows "Sign in" / "Get started" again
- [ ] After logout, `/login` shows the form again rather than redirecting
- [ ] The session cookie does not contain the password or its hash
- [ ] `venv/Scripts/python -m pytest` passes, including the new login/logout tests
