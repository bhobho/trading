"""
routers/admin.py — Admin-only user management routes.
All routes are protected by the require_admin dependency.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from routers.auth import require_admin, hash_password

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/users", response_class=HTMLResponse)
async def list_users(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return templates.TemplateResponse(request=request, name="admin/users.html", context=
        {
            "request": request,
            "user": admin,
            "users": users,
            "toast": request.query_params.get("toast"),
        },
    )


@router.post("/users/create", response_class=HTMLResponse)
async def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(default="user"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # Check uniqueness
    existing = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing:
        users = db.query(User).order_by(User.created_at.desc()).all()
        return templates.TemplateResponse(request=request, name="admin/users.html", context=
            {
                "request": request,
                "user": admin,
                "users": users,
                "error": "Username or email already exists.",
                "toast": None,
            },
        )

    new_user = User(
        username=username.strip(),
        email=email.strip().lower(),
        hashed_password=hash_password(password),
        role=role if role in ("admin", "user") else "user",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/admin/users?toast=User+created", status_code=302)


@router.post("/users/{user_id}/edit")
async def edit_user(
    user_id: int,
    role: str = Form(...),
    is_active: str = Form(default="off"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deactivating themselves
    if target.id == admin.id and is_active != "on":
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    target.role = role if role in ("admin", "user") else "user"
    target.is_active = is_active == "on"
    db.commit()
    return RedirectResponse(url="/admin/users?toast=User+updated", status_code=302)


@router.post("/users/{user_id}/delete")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    # Soft delete: preserve trade history
    target.is_active = False
    db.commit()
    return RedirectResponse(url="/admin/users?toast=User+deactivated", status_code=302)


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.hashed_password = hash_password(new_password)
    db.commit()
    return RedirectResponse(url="/admin/users?toast=Password+reset", status_code=302)
