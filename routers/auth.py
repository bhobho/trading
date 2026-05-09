"""
routers/auth.py — Authentication routes: login, logout, register, change password.
Uses Starlette session middleware for cookie-based sessions (no JWT).
"""
from datetime import datetime

import bcrypt
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Dependency: returns the User object for the logged-in session, or None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency: redirects to login if not authenticated."""
    user = get_current_user(request, db)
    if not user:
        raise _NeedsLogin()
    return user


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency: redirects to dashboard if authenticated but not admin."""
    user = require_user(request, db)
    if not user.is_admin():
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


from starlette.exceptions import HTTPException as StarletteHTTPException

class _NeedsLogin(StarletteHTTPException):
    def __init__(self):
        super().__init__(status_code=302)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request=request, name="login.html", context= {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(request=request, name="login.html", context= {"request": request, "error": "Invalid username or password"}
        )

    # Update last_login timestamp
    user.last_login = datetime.utcnow()
    db.commit()

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["role"] = user.role

    # Flag if this is the default admin password so we can show the setup banner
    if username == "admin" and verify_password("admin123", user.hashed_password):
        request.session["default_password_warning"] = True

    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(request=request, name="change_password.html", context= {"request": request, "user": user, "error": None, "success": False}
    )


@router.post("/change-password", response_class=HTMLResponse)
async def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if not verify_password(current_password, user.hashed_password):
        return templates.TemplateResponse(request=request, name="change_password.html", context=
            {"request": request, "user": user, "error": "Current password is incorrect", "success": False},
        )
    if new_password != confirm_password:
        return templates.TemplateResponse(request=request, name="change_password.html", context=
            {"request": request, "user": user, "error": "New passwords do not match", "success": False},
        )
    if len(new_password) < 8:
        return templates.TemplateResponse(request=request, name="change_password.html", context=
            {"request": request, "user": user, "error": "Password must be at least 8 characters", "success": False},
        )

    user.hashed_password = hash_password(new_password)
    db.commit()

    # Clear the default-password warning from the session
    request.session.pop("default_password_warning", None)

    return templates.TemplateResponse(request=request, name="change_password.html", context=
        {"request": request, "user": user, "error": None, "success": True},
    )
