"""
routers/auth.py — Authentication routes: login, logout, register, email verification.
"""
import secrets
import logging
from datetime import datetime

import bcrypt
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from templates_config import templates
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from database import get_db
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Dependencies ─────────────────────────────────────────────────────────────

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Returns the User object for the logged-in session, or None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user

def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Redirects to login if not authenticated."""
    user = get_current_user(request, db)
    if not user:
        raise _NeedsLogin()
    return user

def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """Redirects to dashboard if authenticated but not admin."""
    user = require_user(request, db)
    if not user.is_admin():
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

class _NeedsLogin(StarletteHTTPException):
    def __init__(self):
        super().__init__(status_code=302)

# ── Helpers ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None, message: str | None = None):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"request": request, "error": error, "message": message}
    )

@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip()
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request=request, name="login.html", 
            context={"request": request, "error": "Invalid username or password"}
        )


    user.last_login = datetime.utcnow()
    db.commit()

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["role"] = user.role

    if username == "admin" and verify_password("admin123", user.hashed_password):
        request.session["default_password_warning"] = True

    return RedirectResponse(url="/", status_code=302)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/guest")
async def login_guest(request: Request, db: Session = Depends(get_db)):
    guest = db.query(User).filter(User.username == "guest").first()
    if not guest:
        return RedirectResponse(url="/auth/login?error=Guest+mode+unavailable", status_code=302)
    
    request.session["user_id"] = guest.id
    request.session["username"] = "Guest"
    request.session["role"] = "user"
    return RedirectResponse(url="/", status_code=302)

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request=request, name="register.html", context={"request": request, "error": None})

@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if len(password) < 8:
        return templates.TemplateResponse(request=request, name="register.html", context={"request": request, "error": "Password must be at least 8 characters"})
    
    existing = db.query(User).filter((User.username == username) | (User.email == email.lower())).first()
    if existing:
        return templates.TemplateResponse(request=request, name="register.html", context={"request": request, "error": "Username or email already exists"})

    new_user = User(
        username=username.strip(),
        email=email.strip().lower(),
        hashed_password=hash_password(password),
        role="user",
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    
    # Log in immediately after registration
    request.session["user_id"] = new_user.id
    request.session["username"] = new_user.username
    request.session["role"] = new_user.role

    return RedirectResponse(url="/", status_code=302)


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(request=request, name="profile.html", context={"request": request, "user": user})

@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(request=request, name="change_password.html", context= {"request": request, "user": user, "error": None, "success": False})

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
        return templates.TemplateResponse(request=request, name="change_password.html", context={"request": request, "user": user, "error": "Current password is incorrect", "success": False})
    if new_password != confirm_password:
        return templates.TemplateResponse(request=request, name="change_password.html", context={"request": request, "user": user, "error": "New passwords do not match", "success": False})
    if len(new_password) < 8:
        return templates.TemplateResponse(request=request, name="change_password.html", context={"request": request, "user": user, "error": "Password must be at least 8 characters", "success": False})

    user.hashed_password = hash_password(new_password)
    db.commit()
    request.session.pop("default_password_warning", None)

    return templates.TemplateResponse(request=request, name="change_password.html", context={"request": request, "user": user, "error": None, "success": True})
