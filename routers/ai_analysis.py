"""
routers/ai_analysis.py — Claude-like interface to run Technical Analysis via DeepSeek.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from routers.auth import require_user
from models.user import User
from services.ai_service import generate_technical_analysis

router = APIRouter()
templates = Jinja2Templates(directory="templates")

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
            "analysis": None,
            "error": None,
            "loading": False,
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
            "analysis": analysis_markdown,
            "error": None,
            "loading": False,
        }
    )
