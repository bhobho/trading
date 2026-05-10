"""
templates.py — Shared Jinja2 templates instance for the application.
"""
from fastapi.templating import Jinja2Templates
from services.market_service import get_market_ticker_data

templates = Jinja2Templates(directory="templates")

def market_data_processor(request):
    """
    Injects live market data into every template context.
    """
    return {"market_data": get_market_ticker_data()}

templates.context_processors.append(market_data_processor)
