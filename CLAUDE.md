# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Spendly: a Flask + SQLite personal expense tracker (amounts in ₹), built as a step-by-step tutorial skeleton. Most of the app is not implemented yet; check `app.py` and `database/db.py` for what exists before assuming a feature is present.

## Commands

Windows with a venv at `venv/` (not activated between Bash calls, so call its tools directly):

```
venv/Scripts/pip install -r requirements.txt
venv/Scripts/python app.py          # dev server, debug mode, http://127.0.0.1:5001 (port 5001, not 5000)
venv/Scripts/python -m pytest       # pytest + pytest-flask are installed, but no tests exist yet
venv/Scripts/python -m pytest path/to/test_file.py::test_name   # single test
```

There is no linter or build step configured.

## Architecture

- `app.py`: single Flask module holding every route. Implemented routes only render templates (`/`, `/register`, `/login`, `/terms`, `/privacy`). `/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete` are placeholders that return strings labelled with tutorial step numbers ("Step 3", "Step 4", "Step 7", "Step 8", "Step 9"); replace them in place rather than adding new routes.
- `database/db.py`: plain `sqlite3`, no ORM. `get_db()` returns a connection with `row_factory` and foreign keys on; `init_db()` creates the `users` and `expenses` tables (`CREATE TABLE IF NOT EXISTS`); `seed_db()` adds a demo user (`demo@spendly.com` / `demo123`) and 8 sample expenses, and does nothing if users already exist. `app.py` calls `init_db()` and `seed_db()` on startup. The DB file `spendly.db` (project root) is gitignored via `*.db`.
- `templates/`: Jinja2 pages extending `base.html` (navbar, footer, Google Fonts, `style.css`, `main.js`). Blocks: `title`, `head`, `content`. Link with `url_for(...)` using the route function names (`landing`, `login`, `register`, ...), so renaming a view function breaks templates.
- `static/css/style.css` is the global stylesheet; `static/css/landing.css` holds landing-page-only styles. `static/js/main.js` is a one-line placeholder.
- The `register.html` and `login.html` forms use `method="POST"`, but their routes only accept GET, so submitting them returns 405 until the routes get `methods=["GET", "POST"]`.

## Notes

- `first.txt` is a pasted terminal transcript from an earlier session, not project documentation.
- Main branch is `main`; remote is `Gauravtechstack/spendly` on GitHub. Recent work is landing-page commits prefixed `landing:`.
