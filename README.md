# CSP Analyzer

A full-stack web application for analyzing, screening, and journaling **Cash-Secured Put (CSP)** options trades.

Built with FastAPI + Jinja2 + Tailwind CSS + SQLite. Runs locally with zero configuration and deploys to any Python-friendly cloud platform with minimal changes.

---

## Features

- **CSP Screener** — Fetch live options chains via yfinance, score each put contract 0–100 using a composite formula (annualized return, OTM %, open interest, IV), filter by delta/DTE/return, sort and color-code results.
- **Trade Journal** — Log, track, and close CSP trades. See unrealized P&L on open positions, realized P&L on closed ones, and portfolio-level statistics.
- **Dashboard** — Portfolio summary cards, upcoming expirations table, monthly premium bar chart.
- **Admin Panel** — Create, edit, deactivate, and reset passwords for users (admin role only).
- **Session Auth** — Cookie-based sessions with bcrypt password hashing. First-run auto-creates `admin/admin123` with a change-password prompt.

---

## Quick Start (local)

```bash
# 1. Clone / download the project
cd csp_analyzer

# 2. (Optional) Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Copy and edit the env file
cp .env.example .env

# 5. Run
python main.py
```

Open **http://localhost:8000** — log in with `admin` / `admin123` and change the password when prompted.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./csp_analyzer.db` | SQLAlchemy DB URL. Use PostgreSQL URL for cloud. |
| `SECRET_KEY` | *(random — changes each restart)* | Session signing key. **Set a fixed value in production.** |
| `SESSION_MAX_AGE` | `604800` (7 days) | Session cookie lifetime in seconds. |
| `DEBUG` | `false` | Enable uvicorn hot-reload and API docs at `/api/docs`. |
| `HOST` | `0.0.0.0` | Bind host. |
| `PORT` | `8000` | Bind port. |
| `PRICE_REFRESH_INTERVAL` | `300` | Background price-refresh tick in seconds. |
| `DEFAULT_ADMIN_USER` | `admin` | First-run admin username. |
| `DEFAULT_ADMIN_PASS` | `admin123` | First-run admin password. |
| `DEFAULT_ADMIN_EMAIL` | `admin@localhost` | First-run admin email. |

---

## Docker

```bash
# Build and run with docker-compose
docker compose up --build

# Or with plain Docker
docker build -t csp-analyzer .
docker run -p 8000:8000 -e SECRET_KEY=yourkey -v csp_data:/app/data csp-analyzer
```

---

## Cloud Deployment

### Railway / Render / Fly.io

All three platforms support Python apps natively. General steps:

1. **Set env vars** in the platform dashboard (at minimum `SECRET_KEY` and `DATABASE_URL`).
2. **PostgreSQL** — Provision a Postgres add-on and set `DATABASE_URL=postgresql://...`. SQLAlchemy handles the rest; no code changes required.
3. **Deploy** — Push to GitHub and connect your repo, or use the platform CLI.

#### Railway

```bash
railway login
railway init
railway add --plugin postgresql
railway vars set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
railway up
```

#### Render

- Create a new **Web Service**, connect your repo.
- Set **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Add env vars in the dashboard.
- Add a **PostgreSQL** database and copy its `DATABASE_URL` into the web service env vars.

#### Fly.io

```bash
fly launch          # creates fly.toml
fly secrets set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
fly postgres create --name csp-db
fly postgres attach --app <your-app> csp-db
fly deploy
```

---

## CSP Score Algorithm

Each put contract is scored 0–100 using a weighted composite of four normalised sub-scores:

```
score = (annualised_return_score × 0.4)
      + (otm_pct_score           × 0.3)
      + (open_interest_score     × 0.2)
      + (iv_rank_score           × 0.1)
```

| Component | Normalisation | Rationale |
|---|---|---|
| Annualised return | Linear 0–60 % → 0–100 | Core profitability metric |
| OTM % | Linear 0–20 % → 0–100 | Higher OTM = safer, lower assignment risk |
| Open interest | Log scale, cap 10,000 → 100 | Liquidity proxy |
| IV rank | Triangle peak at 40 % IV | Moderate IV = good premium without panic pricing |

Rows are coloured **green** (≥ 70), **yellow** (50–69), or **red** (< 50).

---

## Project Structure

```
csp_analyzer/
├── main.py                  FastAPI app, lifespan, scheduler, first-run seed
├── config.py                Settings from environment variables
├── database.py              SQLAlchemy engine + session factory
├── models/
│   ├── user.py              User ORM model
│   └── trade.py             CSPTrade ORM model + computed properties
├── routers/
│   ├── auth.py              Login, logout, change password, session helpers
│   ├── dashboard.py         Home dashboard
│   ├── analyzer.py          CSP screener (calls options_service)
│   ├── trades.py            Trade journal CRUD
│   └── admin.py             User management (admin only)
├── services/
│   ├── options_service.py   yfinance fetching + CSP scoring algorithm
│   └── trade_service.py     Trade P&L calculations + portfolio summary
├── templates/               Jinja2 HTML templates
├── static/                  Optional static overrides
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## License

MIT
# trading
