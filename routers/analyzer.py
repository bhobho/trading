"""
routers/analyzer.py — CSP Screener / Analyzer.
Accepts ticker(s) + filter params, calls options_service, returns results table.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import require_user
from models.user import User
from services.options_service import get_csp_opportunities, get_current_price
router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def analyzer_page(request: Request, user: User = Depends(require_user)):
    """Show empty analyzer form."""
    return templates.TemplateResponse(request=request, name="analyzer.html", context=
        {
            "request": request,
            "user": user,
            "results": None,
            "params": {},
            "error": None,
            "loading": False,
        },
    )


@router.post("/", response_class=HTMLResponse)
async def analyzer_run(
    request: Request,
    tickers: str = Form(...),
    min_premium_pct: float = Form(default=15.0),
    max_delta: float = Form(default=0.30),
    min_dte: int = Form(default=7),
    max_dte: int = Form(default=45),
    min_score: float = Form(default=50.0),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Run the screener for the given tickers and filter params."""
    params = {
        "tickers": tickers,
        "min_premium_pct": min_premium_pct,
        "max_delta": max_delta,
        "min_dte": min_dte,
        "max_dte": max_dte,
        "min_score": min_score,
    }

    # Support comma or space-separated tickers
    ticker_list = [t.strip().upper() for t in tickers.replace(",", " ").split() if t.strip()]

    if not ticker_list:
        return templates.TemplateResponse(request=request, name="analyzer.html", context=
            {
                "request": request,
                "user": user,
                "results": None,
                "params": params,
                "error": "Please enter at least one ticker symbol.",
                "loading": False,
            },
        )

    all_results = []
    errors = []
    current_prices = {}

    for ticker in ticker_list[:10]:  # Cap at 10 tickers to prevent abuse
        price = get_current_price(ticker)
        if price:
            current_prices[ticker] = price

        results = get_csp_opportunities(
            ticker=ticker,
            min_premium_pct=min_premium_pct,
            max_delta=max_delta,
            min_dte=min_dte,
            max_dte=max_dte,
            min_score=min_score,
        )
        if results:
            all_results.extend(results)
        else:
            errors.append(f"No data returned for {ticker}")

    # Re-sort combined results from multiple tickers by CSP Score
    all_results.sort(key=lambda x: x["csp_score"], reverse=True)

    error_msg = "; ".join(errors) if errors and not all_results else None

    return templates.TemplateResponse(request=request, name="analyzer.html", context=
        {
            "request": request,
            "user": user,
            "results": all_results,
            "params": params,
            "current_prices": current_prices,
            "error": error_msg,
            "loading": False,
        },
    )
