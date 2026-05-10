"""
routers/dashboard.py — Home dashboard showing portfolio summary, upcoming expirations,
and monthly premium chart data.
"""
import json
import yfinance as yf
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from templates_config import templates
from database import get_db
from models.trade import CSPTrade
from routers.auth import require_user
from models.user import User
from services.trade_service import get_portfolio_summary

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    trades = db.query(CSPTrade).filter(CSPTrade.user_id == user.id).all()
    summary = get_portfolio_summary(trades)

    # Prepare chart data (last 12 months, ordered chronologically)
    monthly = summary["monthly_premium"]
    chart_labels = list(monthly.keys())
    chart_values = list(monthly.values())

    # Recent activity: last 10 trades ordered by created_at desc
    recent_trades = (
        db.query(CSPTrade)
        .filter(CSPTrade.user_id == user.id)
        .order_by(CSPTrade.created_at.desc())
        .limit(10)
        .all()
    )
    
    return templates.TemplateResponse(request=request, name="dashboard.html", context=
        {
            "request": request,
            "user": user,
            "summary": summary,
            "upcoming": summary["upcoming_expirations"],
            "recent_trades": recent_trades,
            "chart_labels": json.dumps(chart_labels),
            "chart_values": json.dumps(chart_values),
            "default_password_warning": request.session.get("default_password_warning", False),
        },
    )
