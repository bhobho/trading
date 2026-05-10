"""
routers/trades.py — Trade journal: list, create, edit, delete CSP trades.
"""
from datetime import date, datetime
import csv
import io
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from templates_config import templates
from sqlalchemy.orm import Session

from database import get_db
from models.trade import CSPTrade
from routers.auth import require_user
from models.user import User
from services.trade_service import enrich_trades_batch, get_journal_summary

router = APIRouter()


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
    collateral: float | None = Form(default=None),
    delta: float | None = Form(default=None),
    iv: float | None = Form(default=None),
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
        collateral=collateral,
        delta=delta,
        iv=iv,
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


@router.get("/export")
async def export_trades(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Export all trades for the current user as a CSV file."""
    trades = db.query(CSPTrade).filter(CSPTrade.user_id == user.id).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        "ticker", "strike_price", "expiration_date", "num_contracts", 
        "premium_received", "open_date", "status", "close_premium", 
        "close_date", "collateral", "delta", "iv", "notes"
    ])
    
    for t in trades:
        writer.writerow([
            t.ticker, t.strike_price, t.expiration_date.isoformat(), t.num_contracts,
            t.premium_received, t.open_date.isoformat(), t.status,
            t.close_premium if t.close_premium is not None else "",
            t.close_date.isoformat() if t.close_date else "",
            t.collateral if t.collateral is not None else "",
            t.delta if t.delta is not None else "",
            t.iv if t.iv is not None else "",
            t.notes or ""
        ])
    
    output.seek(0)
    headers = {
        'Content-Disposition': f'attachment; filename="trades_export_{date.today().isoformat()}.csv"'
    }
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)


@router.post("/import", response_class=HTMLResponse)
async def import_trades(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Import trades from a CSV file."""
    if not file.filename.endswith('.csv'):
        return RedirectResponse(url="/trades/?toast=Error:+Only+CSV+files+allowed", status_code=302)
    
    try:
        content = await file.read()
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        
        count = 0
        for row in reader:
            try:
                # Basic validation and type conversion
                ticker = row['ticker'].strip().upper()
                strike = float(row['strike_price'])
                exp_date = date.fromisoformat(row['expiration_date'])
                contracts = int(row['num_contracts'])
                premium = float(row['premium_received'])
                open_d = date.fromisoformat(row['open_date'])
                status = row['status'].strip().lower()
                
                close_p = row.get('close_premium', '').strip()
                close_premium = float(close_p) if close_p else None
                
                close_d = row.get('close_date', '').strip()
                close_date_val = date.fromisoformat(close_d) if close_d else None
                
                notes = row.get('notes', '').strip() or None
                
                collat = row.get('collateral', '').strip()
                collateral_val = float(collat) if collat else None
                
                delta_str = row.get('delta', '').strip()
                delta_val = float(delta_str) if delta_str else None
                
                iv_str = row.get('iv', '').strip()
                iv_val = float(iv_str) if iv_str else None

                trade = CSPTrade(
                    user_id=user.id,
                    ticker=ticker,
                    strike_price=strike,
                    expiration_date=exp_date,
                    num_contracts=contracts,
                    premium_received=premium,
                    open_date=open_d,
                    status=status,
                    close_premium=close_premium,
                    close_date=close_date_val,
                    collateral=collateral_val,
                    delta=delta_val,
                    iv=iv_val,
                    notes=notes
                )
                db.add(trade)
                count += 1
            except (KeyError, ValueError) as e:
                # Skip invalid rows
                continue
        
        db.commit()
        return RedirectResponse(url=f"/trades/?toast=Successfully+imported+{count}+trades", status_code=302)
        
    except Exception as e:
        return RedirectResponse(url="/trades/?toast=Error+parsing+CSV+file", status_code=302)


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
