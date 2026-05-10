"""
main.py — FastAPI application entrypoint.

Responsibilities:
  - Create the FastAPI app and mount middleware (sessions, static files)
  - Register all routers
  - Create DB tables and seed the default admin user on first run
  - Start the APScheduler background task for refreshing open-trade prices
  - Serve the app via uvicorn when run directly
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from database import Base, SessionLocal, engine
import secrets

# Import models so SQLAlchemy registers them before create_all
from models.user import User  # noqa: F401
from models.trade import CSPTrade  # noqa: F401

from routers import auth, dashboard, analyzer, trades, admin, ai_analysis

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)


# ── Background price refresh ─────────────────────────────────────────────────

def refresh_open_trade_prices():
    """
    Periodically called by APScheduler.
    We don't persist live prices — they're fetched on demand in trade_service.
    This function just logs activity and could be extended to cache prices.
    """
    db = SessionLocal()
    try:
        count = db.query(CSPTrade).filter(CSPTrade.status == "open").count()
        if count > 0:
            logger.info("Price refresh tick — %d open trades in portfolio", count)
    except Exception as e:
        logger.warning("Price refresh error: %s", e)
    finally:
        db.close()


# ── First-run seed ────────────────────────────────────────────────────────────

def seed_default_admin():
    """
    If no users exist, create the default admin/admin123 account.
    A warning banner in the UI will prompt the user to change this password.
    """
    from routers.auth import hash_password

    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                username=settings.DEFAULT_ADMIN_USER,
                email=settings.DEFAULT_ADMIN_EMAIL,
                hashed_password=hash_password(settings.DEFAULT_ADMIN_PASS),
                role="admin",
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow(),
            )
            db.add(admin)
            db.commit()
            logger.info(
                "First-run: created default admin user '%s'. PLEASE CHANGE THE PASSWORD.",
                settings.DEFAULT_ADMIN_USER,
            )
    finally:
        db.close()


def cleanup_guest_data():
    """
    Remove all trades associated with the 'guest' user on startup.
    This ensures guest data doesn't persist across server restarts.
    """
    db = SessionLocal()
    try:
        from models.trade import CSPTrade
        guest = db.query(User).filter(User.username == "guest").first()
        if guest:
            db.query(CSPTrade).filter(CSPTrade.user_id == guest.id).delete()
            db.commit()
            logger.info("Cleanup: cleared all guest trades from database.")
        else:
            # Create the guest user if it doesn't exist
            from routers.auth import hash_password
            import secrets
            guest = User(
                username="guest",
                email="guest@example.com",
                hashed_password=hash_password(secrets.token_urlsafe(32)),
                role="user",
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow(),
            )
            db.add(guest)
            db.commit()
            logger.info("Startup: initialized guest user account.")
    except Exception as e:
        logger.error("Failed to cleanup guest data: %s", e)
    finally:
        db.close()


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    seed_default_admin()
    cleanup_guest_data()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        refresh_open_trade_prices,
        "interval",
        seconds=settings.PRICE_REFRESH_INTERVAL,
        id="price_refresh",
    )
    scheduler.start()
    logger.info("APScheduler started — price refresh every %ds", settings.PRICE_REFRESH_INTERVAL)

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description="Cash-Secured Put options trade analyzer and journal",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url=None,
)

# Session middleware — random secret key on each restart to force login
app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_urlsafe(64),
    max_age=settings.SESSION_MAX_AGE,
    https_only=False,
    same_site="lax",
)

# Static files (CSS overrides, favicons, etc.)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    pass  # static/ dir is optional; skip if missing

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(dashboard.router, prefix="", tags=["dashboard"])
app.include_router(analyzer.router, prefix="/analyzer", tags=["analyzer"])
app.include_router(ai_analysis.router, prefix="/ai-analysis", tags=["ai_analysis"])
app.include_router(trades.router, prefix="/trades", tags=["trades"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


# ── Auth redirect exception handler ──────────────────────────────────────────
# _NeedsLogin (status 302) raised by require_user/require_admin dependencies
# must be caught here and turned into an actual redirect response.
# Raising a Response directly inside a Depends() crashes the ASGI layer.
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    from routers.auth import _NeedsLogin
    if isinstance(exc, _NeedsLogin):
        return RedirectResponse(url="/auth/login", status_code=302)
    # Re-raise all other HTTP exceptions using FastAPI's default handler
    from fastapi.exception_handlers import http_exception_handler as _default
    return await _default(request, exc)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )