# K0IRO Summer of Simplex — Scoring Application

A Flask-based contest scoring web application for the K0IRO Summer of Simplex event.
Participants submit simplex contacts via a public web form; scores are calculated automatically
and displayed on a live leaderboard. Admins can manage submissions and apply bonus multipliers
through a protected dashboard.

---

## Tech Stack

- **Python 3.11+**
- **Flask 3.x** — web framework
- **Flask-SQLAlchemy** — ORM / database layer
- **SQLite** — database (file stored in `instance/`)
- **Werkzeug** — password hashing
- **python-dotenv** — environment variable management
- **pyenv** — recommended Python version manager

---

## Project Structure

```
simplex/
├── run.py                  # App entry point
├── create_admin.py         # One-time admin user creation script
├── requirements.txt
├── .env                    # Environment variables (not committed)
├── .gitignore
├── instance/
│   └── simplex.db          # SQLite database (auto-created, not committed)
└── app/
    ├── __init__.py         # App factory
    ├── models.py           # Database models
    ├── routing.py          # All route handlers
    ├── scoring.py          # Scoring logic
    ├── client_auth.py      # Auth decorators (login_required, admin_required)
    ├── static/
    │   ├── css/
    │   │   └── style.css
    │   └── img/
    │       └── logo.svg
    └── templates/
        ├── base.html
        ├── index.html
        ├── submit.html
        ├── leaderboard.html
        ├── login.html
        ├── admin_home.html
        ├── admin_submissions.html
        ├── admin_deleted.html
        ├── scoring_overview.html
        ├── set_multiplier.html
        └── admin_reset.html
```

---

## Setup

### 1. Prerequisites

Ensure you have [pyenv](https://github.com/pyenv/pyenv) installed, along with
[pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv).

### 2. Create and activate a virtual environment

```bash
pyenv virtualenv 3.11.9 simplex
pyenv activate simplex
```

To auto-activate when entering the project directory:

```bash
cd simplex
pyenv local simplex
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-random-secret-key-here
```

Generate a strong secret key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Note:** Never commit `.env` to version control. It is listed in `.gitignore`.

### 5. Create the first admin user

The database is created automatically on first run. After starting the app at least
once (or running the factory directly), create your admin account:

```bash
python create_admin.py
```

You will be prompted for a callsign and password. The script can be re-run at any
time to reset a password or add additional admin accounts.

### 6. Run the development server

```bash
flask --app run run --debug
```

The app will be available at `http://localhost:5000`.

---

## Admin Access

The admin login page is intentionally not linked in the navigation. To access it,
navigate directly to:

```
http://localhost:5000/login
```

After logging in, an **Admin** link will appear in the nav bar. Admin features include:

- View and soft-delete submissions (with restore and audit trail)
- Scoring overview with per-operator daily breakdown split by Voice and Digital
- Apply bonus score multipliers per operator per day
- Master reset (wipes all submissions and scores)

---

## Scoring Rules

| Activity | Points |
|---|:---:|
| Voice simplex contact (Ham or GMRS) | 1 |
| Digital simplex contact (SSTV, PSK, RTTY, FT4/8, JS8, Winlink) | 1 |
| Voice simplex contact from a POTA park | 2 |

Admin-applied daily bonus multipliers stack on top of base scores.

---

## Deployment Notes

For production deployment:

- Set `SECRET_KEY` to a strong random value in `.env`
- Run behind a WSGI server such as **gunicorn**:
  ```bash
  pip install gunicorn
  gunicorn -w 4 "run:app"
  ```
- Put a reverse proxy (nginx, Caddy) in front of gunicorn to handle HTTPS
- The `instance/` folder (containing the SQLite database) should be persisted
  and backed up — it is not committed to version control

---

## Environment Variables

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `SECRET_KEY` | Yes | `devkey-change-in-production` | Flask session signing key |

---

## License

Internal use — K0IRO Iowa Radio Operators.