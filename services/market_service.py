"""
services/market_service.py — Fetches and caches live market ticker data.
"""
import logging
import time
import yfinance as yf

logger = logging.getLogger(__name__)

# Simple in-memory cache
_market_cache = {
    "data": [],
    "last_updated": 0
}
CACHE_TTL = 300 # 5 minutes

def get_market_ticker_data():
    """
    Fetches indices and top stocks. Caches for CACHE_TTL seconds.
    """
    now = time.time()
    if _market_cache["data"] and (now - _market_cache["last_updated"]) < CACHE_TTL:
        return _market_cache["data"]

    indices = {"^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones"}
    top_stocks = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "UNH", "V",
        "JNJ", "XOM", "WMT", "JPM", "MA", "PG", "AVGO", "HD", "CVX", "ORCL"
    ]
    all_tickers = list(indices.keys()) + top_stocks
    
    market_data = []
    try:
        # Fetch last 2 days to calculate change
        data = yf.download(all_tickers, period="2d", interval="1d", progress=False)
        
        # Process Indices
        for symbol, name in indices.items():
            if symbol in data['Close']:
                current = data['Close'][symbol].iloc[-1]
                prev = data['Close'][symbol].iloc[-2]
                if current > 0 and prev > 0:
                    change_pct = ((current - prev) / prev) * 100
                    market_data.append({
                        "name": name,
                        "symbol": symbol,
                        "price": round(current, 2),
                        "change_pct": round(change_pct, 2),
                        "is_index": True
                    })
        
        # Process Stocks
        for symbol in top_stocks:
            if symbol in data['Close']:
                current = data['Close'][symbol].iloc[-1]
                prev = data['Close'][symbol].iloc[-2]
                if current > 0 and prev > 0:
                    change_pct = ((current - prev) / prev) * 100
                    market_data.append({
                        "name": symbol,
                        "symbol": symbol,
                        "price": round(current, 2),
                        "change_pct": round(change_pct, 2),
                        "is_index": False
                    })
        
        _market_cache["data"] = market_data
        _market_cache["last_updated"] = now
        return market_data
        
    except Exception as e:
        logger.warning("Market ticker fetch failed: %s", e)
        return _market_cache["data"] # Return stale data if fetch fails
