# Spec: Profile Page Design

## Overview
Replace the `/profile` placeholder ("Profile page — coming in Step 4") with a real, designed profile page for the signed-in user. Login (Step 3) already redirects to `/profile`, so this is the first page a user sees after authenticating. The page shows who the user is (name, email, member-since date), a summary of their spending (total spent, number of expenses, top category), and a table of their recent expenses with amounts in ₹. It is read-only: adding, editing and deleting expenses belong to Steps 7–9. It also introduces the first access control in the app: logged-out visitors are redirected to `/login`.

## Depends on
- Step 01 — Database setup (`users` and `expenses` tables, `get_db()`, seeded demo data).
- Step 02 — Registration (real users can exist with no expenses).
- Step 03 — Login and logout (`session["user_id"]`, redirect to `/profile` after login).

## Routes
- `GET /profile` — render the profile page for the current user; redirect to `/login` if not logged in — logged-in (existing placeholder, replaced in place)

No new view functions. Replace the body of the existing `profile` view in `app.py`; do not rename it (`login` already uses `url_for("profile")`).

## Database changes
No database changes. The existing tables are sufficient:
- `users` (`id`, `name`, `email`, `password_hash`, `created_at`) — name, email and member-since date. `password_hash` must never be selected for this page.
- `expenses` (`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`) — totals, top category and the recent list, always filtered by `user_id`.

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; sections: profile header (avatar with the user's initial, name, email, "Member since"), summary stat cards (Total spent, Expenses, Top category), recent expenses table (date, description, category, amount) with an empty state when the user has no expenses.
- **Modify:**
  - `templates/base.html` — add a "Profile" link to `url_for('profile')` in `.nav-links` when `session.get('user_id')` is set, before "Sign out"; give both links the class `nav-keep`; load Lucide icons from a version-pinned CDN script and call `lucide.createIcons()`.
  - `static/css/style.css` — change the mobile rule to `.nav-links a:not(.nav-cta):not(.nav-keep)` so Profile and Sign out stay visible on small screens.

## Files to change
- `app.py` — implement the `profile` view (session check, user lookup, summary and recent-expense queries, render template).
- `templates/base.html` — navbar "Profile" link for signed-in users.
- `static/css/style.css` — only if a small shared style is needed; otherwise keep page styles in the new `profile.css`.

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — profile-page-only styles, loaded through the `head` block of `profile.html` (same pattern as `landing.css`).
- `tests/test_profile.py` — pytest tests for the profile page (temporary database, following `tests/test_login_logout.py`).

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — plain `sqlite3` via `get_db()`
- Parameterised queries only — never build SQL with string formatting or f-strings
- Passwords hashed with werkzeug; never select, render or log `password_hash`
- Use CSS variables — never hardcode hex values (reuse `--accent`, `--paper-card`, `--border`, `--ink-muted`, `--font-display`, `--radius-md`, etc. from `style.css`)
- All templates extend `base.html`
- Replace the existing `profile` view in place; do not add routes or rename view functions
- If `session.get("user_id")` is missing, `redirect(url_for("login"))`
- If the session's user id no longer exists in `users`, clear the session and redirect to `/login`
- Every expense query must filter on `user_id = ?` using the session id so users only see their own data
- Compute totals in SQL (`SUM`, `COUNT`, `GROUP BY category`); show the 10 most recent expenses ordered by `date DESC, id DESC`
- Format amounts as `₹` with thousands separators and two decimals (e.g. `₹2,999.00`); format dates as `DD Mon YYYY`
- Jinja autoescaping stays on; never mark user-supplied name, email or description as `|safe`
- Always close the DB connection in a `finally` block, as `database/db.py` does
- Layout must stay usable on narrow screens (stat cards stack, table scrolls or reflows)
- Do not build add/edit/delete expense UI, filters, charts, avatar upload or profile editing here

## Definition of done
- [ ] `venv/Scripts/python app.py` starts without errors
- [ ] Visiting `/profile` while logged out redirects (302) to `/login`
- [ ] Logging in as `demo@spendly.com` / `demo123` lands on a designed profile page, not the placeholder string
- [ ] The header shows the user's name, email, an initial avatar and a "Member since" date
- [ ] Summary cards show Total spent (₹, matching the sum of the demo expenses, 6,694.50), Expenses count (8) and Top category (Shopping)
- [ ] The recent expenses table lists the demo expenses newest first with date, description, category and ₹ amount
- [ ] A newly registered user with no expenses sees the empty state and ₹0.00 / 0 in the summary, with no errors
- [ ] A user never sees another user's expenses (verified with two accounts)
- [ ] The navbar shows "Profile" and "Sign out" when logged in, and neither when logged out
- [ ] The page renders correctly at a narrow (mobile) width and uses the existing Spendly look (fonts, colours)
- [ ] At 600px wide or less, "Profile" and "Sign out" are still visible when logged in
- [ ] Lucide icons render on the page (stat cards, member-since line)
- [ ] No hardcoded hex colours appear in `profile.css`
- [ ] `venv/Scripts/python -m pytest` passes, including the new profile tests
