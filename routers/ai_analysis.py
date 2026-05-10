"""
routers/ai_analysis.py — Claude-powered Technical Analysis interface.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from templates_config import templates
from routers.auth import require_user
from models.user import User
from services.ai_service import generate_technical_analysis, parse_csp_query
from services.options_service import get_csp_opportunities

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def ai_analysis_page(request: Request, user: User = Depends(require_user)):
    """Show the empty AI Analysis interface."""
    return templates.TemplateResponse(
        request=request, 
        name="ai_analysis.html", 
        context={
            "request": request,
            "user": user,
            "ticker": "",
            "query": "",
            "analysis": None,
            "opportunities": None,
            "params": None,
            "error": None,
            "loading": False,
            "mode": "analysis", # 'analysis' or 'search'
        }
    )

@router.post("/", response_class=HTMLResponse)
async def ai_analysis_run(
    request: Request,
    ticker: str = Form(...),
    user: User = Depends(require_user),
):
    """Fetch the analysis and return it."""
    ticker = ticker.strip().upper()
    if not ticker:
        return templates.TemplateResponse(
            request=request, 
            name="ai_analysis.html", 
            context={
                "request": request,
                "user": user,
                "ticker": "",
                "analysis": None,
                "error": "Please enter a valid ticker symbol.",
                "loading": False,
            }
        )

    analysis_markdown = await generate_technical_analysis(ticker)

    return templates.TemplateResponse(
        request=request, 
        name="ai_analysis.html", 
        context={
            "request": request, 
            "user": user,
            "ticker": ticker,
            "query": "",
            "analysis": analysis_markdown,
            "opportunities": None,
            "params": None,
            "error": None,
            "loading": False,
            "mode": "analysis",
        }
    )


@router.post("/search", response_class=HTMLResponse)
async def ai_search_run(
    request: Request,
    query: str = Form(...),
    user: User = Depends(require_user),
):
    """Parse query and search for CSP opportunities."""
    query = query.strip()
    if not query:
        return RedirectResponse(url="/ai-analysis/", status_code=302)

    # 1. Parse query into parameters
    params = await parse_csp_query(query)
    ticker = params.get("ticker")

    if not ticker:
        return templates.TemplateResponse(
            request=request,
            name="ai_analysis.html",
            context={
                "request": request,
                "user": user,
                "ticker": "",
                "query": query,
                "analysis": None,
                "opportunities": None,
                "params": None,
                "error": "I couldn't identify which stock ticker you're interested in. Please try again (e.g., 'Find NVDA puts...').",
                "loading": False,
                "mode": "search",
            }
        )

    # 2. Search for opportunities using the parameters
    # Map AI param names to function argument names
    opportunities = get_csp_opportunities(
        ticker=ticker,
        min_premium_pct=params.get("min_annualized_return", 0.5),
        max_delta=params.get("max_delta", 0.35),
        min_dte=params.get("min_dte", 7),
        max_dte=params.get("max_dte", 45),
        min_score=params.get("min_score", 50.0),
    )

    return templates.TemplateResponse(
        request=request,
        name="ai_analysis.html",
        context={
            "request": request,
            "user": user,
            "ticker": ticker,
            "query": query,
            "analysis": None,
            "opportunities": opportunities,
            "params": params,
            "error": None if opportunities else f"No opportunities found matching those criteria for {ticker}.",
            "loading": False,
            "mode": "search",
        }
    )
