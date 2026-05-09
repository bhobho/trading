"""
routers/trades.py — Trade journal: list, create, edit, delete CSP trades.
"""
from datetime import date, datetime
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models.trade import CSPTrade
from routers.auth import require_user
from models.user import User
from services.trade_service import enrich_trades_batch, get_journal_summary

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _get_trade_or_404(trade_id: int, user_id: int, db: Session) -> CSPTrade:
    """Fetch a trade that belongs to the current user or raise 404."""
    trade = db.query(CSPTrade).filter(
        CSPTrade.id == trade_id, CSPTrade.user_id == user_id
    ).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.get("/", response_class=HTMLResponse)
async def trades_list(
    request: Request,
    status: str | None = None,
    ticker: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    query = db.query(CSPTrade).filter(CSPTrade.user_id == user.id)

    if status and status != "all":
        query = query.filter(CSPTrade.status == status)
    if ticker:
        query = query.filter(CSPTrade.ticker == ticker.upper())

    trades = query.order_by(CSPTrade.open_date.desc()).all()

    # Enrich only open trades with live prices to keep the page snappy;
    # closed trades use stored realized P&L.
    enriched = enrich_trades_batch(trades)
    summary = get_journal_summary(trades)

    # Unique tickers for the filter dropdown
    all_tickers = sorted({t.ticker for t in db.query(CSPTrade).filter(CSPTrade.user_id == user.id).all()})

    return templates.TemplateResponse(request=request, name="trades.html", context=
        {
            "request": request,
            "user": user,
            "trades": enriched,
            "summary": summary,
            "filter_status": status or "all",
            "filter_ticker": ticker or "",
            "all_tickers": all_tickers,
        },
    )


@router.post("/add", response_class=HTMLResponse)
async def add_trade(
    request: Request,
    ticker: str = Form(...),
    strike_price: float = Form(...),
    expiration_date: str = Form(...),
    num_contracts: int = Form(...),
    premium_received: float = Form(...),
    open_date: str = Form(...),
    notes: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    trade = CSPTrade(
        user_id=user.id,
        ticker=ticker.strip().upper(),
        strike_price=strike_price,
        expiration_date=date.fromisoformat(expiration_date),
        num_contracts=num_contracts,
        premium_received=premium_received,
        open_date=date.fromisoformat(open_date),
        notes=notes.strip() or None,
        status="open",
    )
    db.add(trade)
    db.commit()

    return RedirectResponse(url="/trades/?toast=Trade+added+successfully", status_code=302)


@router.get("/{trade_id}/edit", response_class=HTMLResponse)
async def edit_trade_page(
    trade_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    trade = _get_trade_or_404(trade_id, user.id, db)
    return templates.TemplateResponse(request=request, name="trade_edit.html", context= {"request": request, "user": user, "trade": trade}
    )


@router.post("/{trade_id}/edit", response_class=HTMLResponse)
async def edit_trade_submit(
    trade_id: int,
    request: Request,
    status: str = Form(...),
    close_premium: str = Form(default=""),
    close_date: str = Form(default=""),
    notes: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    trade = _get_trade_or_404(trade_id, user.id, db)

    trade.status = status
    trade.notes = notes.strip() or None

    if close_premium.strip():
        trade.close_premium = float(close_premium)
    if close_date.strip():
        trade.close_date = date.fromisoformat(close_date)

    trade.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/trades/?toast=Trade+updated", status_code=302)


@router.post("/{trade_id}/delete")
async def delete_trade(
    trade_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    trade = _get_trade_or_404(trade_id, user.id, db)
    db.delete(trade)
    db.commit()
    return RedirectResponse(url="/trades/?toast=Trade+deleted", status_code=302)
