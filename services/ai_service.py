"""
services/ai_service.py — AI Technical Analysis generator via DeepSeek.
Fetches stock history and queries DeepSeek based on technical indicators.
"""
import logging
from typing import Optional

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

import yfinance as yf

from config import settings

logger = logging.getLogger(__name__)


async def generate_technical_analysis(ticker: str) -> Optional[str]:
    """
    Fetches the last 6 months of OHLC data for the given ticker, 
    and then asks DeepSeek to analyze the technicals for a 2-6 week outlook.
    """
    if not AsyncOpenAI:
        logger.error("OpenAI SDK is not installed. Run `pip install openai`.")
        return "System error: AI SDK missing."

    if not settings.DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY is missing from configuration.")
        return "Configuration error: Missing DeepSeek API key."

    try:
        # Fetch 6-month history metrics instead of dumping endless rows
        tk = yf.Ticker(ticker.upper())
        hist = tk.history(period="6mo")
        if hist.empty:
            return f"No historical data found for {ticker.upper()}."

        # Grab key stats to summarize context instead of sending hundreds of lines
        current_price = hist['Close'].iloc[-1]
        vol_avg = hist['Volume'].mean()
        high_6mo = hist['High'].max()
        low_6mo = hist['Low'].min()

        # Build a constrained prompt to keep analysis focused
        prompt = f"""
I need a technical analysis outlook over the next 2-6 weeks for the stock ticker {ticker.upper()}.
Here is a summary of the past 6 months of data:
- Current Price: ${current_price:.2f}
- 6-Month High: ${high_6mo:.2f}
- 6-Month Low: ${low_6mo:.2f}
- Avg Daily Volume: {vol_avg:,.0f}

Please provide an expert technical analysis. Discuss trendlines, potential support and resistance zones, and what might happen over the next 2-6 weeks. Provide your response as clean, structured Markdown using beautiful formatting (tables, bullet points). Keep your analysis concise but highly actionable.
"""
        
        # Initialize DeepSeek standard config
        client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY, 
            base_url="https://api.deepseek.com"
        )
        
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a professional options trader and technical analyst. You specialize in guiding traders to optimal Cash-Secured Put setups."},
                {"role": "user", "content": prompt}
            ],
            stream=False,
            max_tokens=1000,
            temperature=0.4
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.exception("AI Analysis generation failed for %s", ticker)
        return f"Failed to generate analysis: {e}"
