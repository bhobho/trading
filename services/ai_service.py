"""
services/ai_service.py — AI Technical Analysis generator via Anthropic Claude.
"""
import logging
import json
from typing import Optional, Dict, Any

import anthropic
import yfinance as yf

from config import settings

logger = logging.getLogger(__name__)


def generate_rule_based_analysis(ticker: str, price: float, ma20: float, ma50: float, rsi: float, range_6mo: tuple) -> str:
    """Fallback analysis if AI fails."""
    trend = "Bullish" if price > ma50 else "Bearish"
    # Suggest strike at 6-month low or 10% below current price
    safe_strike = max(range_6mo[0], price * 0.9)
    
    return f"""### Technical Overview for {ticker.upper()} (Safe Mode)
* **Price Action**: {ticker} is trading at ${price:.2f} ({trend} trend).
* **Support**: Key support identified at **${range_6mo[0]:.2f}**.
* **3-5 Week CSP Strategy**: Sell puts at or below **${safe_strike:.2f}** to minimize assignment risk.
*(Note: Automated metrics-based analysis. Claude API currently unavailable.)*
"""

async def generate_technical_analysis(ticker: str) -> Optional[str]:
    """
    Fetches market data and queries Claude for a 3-5 week CSP strategy 
    with a focus on safest strike and assignment risk.
    """
    if not settings.ANTHROPIC_API_KEY:
        return "Configuration error: Missing Anthropic API key."

    try:
        tk = yf.Ticker(ticker.upper())
        hist = tk.history(period="6mo")
        if hist.empty:
            return f"No historical data found for {ticker.upper()}."

        # Robust indicator math
        close = hist['Close']
        diff = close.diff()
        gain = diff.where(diff > 0, 0).tail(14).mean()
        loss = abs(diff.where(diff < 0, 0).tail(14).mean())
        rsi_val = 100 - (100 / (1 + (gain / loss if loss > 0 else 999)))
        current_price = close.iloc[-1]
        volatility = close.pct_change().std() * (252**0.5) * 100
        
        # Earnings check
        next_earnings = "Unknown"
        try:
            calendar = tk.calendar
            if calendar is not None and not calendar.empty:
                next_earnings = calendar.iloc[0, 0].strftime('%Y-%m-%d')
        except: pass

        prompt = f"""
Ticker: {ticker.upper()} | Price: ${current_price:.2f}
RSI: {rsi_val:.1f}
Volatility (HV): {volatility:.1f}% | Next Earnings: {next_earnings}
6mo Low: ${close.min():.2f}

Suggest a **Safest CSP Strike** (3-5 week expiry) to minimize assignment risk.
Output: 3 bullets on Risk/Volatility + 1-sentence "Safest Strike" suggestion.
Be extremely brief.
"""
        
        try:
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            models = ["claude-3-5-sonnet-20240620", "claude-3-5-sonnet-latest", "claude-3-haiku-20240307"]
            
            for model in models:
                try:
                    response = await client.messages.create(
                        model=model,
                        max_tokens=250,
                        temperature=0.1,
                        system="You are a conservative CSP strategist. Minimize tokens.",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return response.content[0].text
                except Exception as e:
                    if "404" not in str(e): raise e
                    continue
            
            raise Exception("404")

        except Exception:
            # Fallback to local rule-based analysis
            ma50 = close.tail(50).mean()
            rsi_val = 50 # Simplified for fallback
            return generate_rule_based_analysis(ticker.upper(), current_price, 0, ma50, rsi_val, (close.min(), close.max()))

    except Exception as e:
        logger.exception("Data fetching failed for %s", ticker)
        return f"Failed to fetch data: {e}"


async def parse_csp_query(query: str) -> Dict[str, Any]:
    """
    Parses a natural language query into structured parameters for CSP searching.
    """
    if not settings.ANTHROPIC_API_KEY:
        return {}

    prompt = f"""
    Parse this CSP query into JSON: "{query}"
    Params: ticker (UPPER), min_annualized_return (float), max_delta (float), min_dte (int), max_dte (int), min_score (float).
    Return ONLY raw JSON.
    """

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=150,
            temperature=0.0,
            system="JSON extractor. Raw JSON only.",
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        return json.loads(content)

    except Exception:
        return {}
