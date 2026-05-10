"""
services/options_service.py — Fetches options chains via yfinance and computes
the CSP Score for each put contract.

Scoring formula:
  score = (annualized_return_score * 0.4)
        + (otm_pct_score          * 0.3)
        + (open_interest_score    * 0.2)
        + (iv_rank_score          * 0.1)

Each component is normalised to 0–100 before weighting so the weights make sense.
"""
from __future__ import annotations

import math
import logging
from datetime import date, datetime
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ── Normalisation helpers ───────────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp value into [lo, hi]."""
    return max(lo, min(hi, value))


def _norm_annualised(ann_pct: float) -> float:
    """
    Map annualised return % → 0–100.
    Assumes a realistic range of 0–60 % annualised. Anything ≥ 60 % scores 100.
    """
    return _clamp(ann_pct / 60.0 * 100)


def _norm_otm(otm_pct: float) -> float:
    """
    Map OTM % → 0–100.
    We reward being OTM (lower delta, safer).  Cap at 20 % OTM = 100 score.
    Strikes deeper than 20 % OTM are still safe but yield very little premium.
    """
    return _clamp(otm_pct / 20.0 * 100)


def _norm_open_interest(oi: int) -> float:
    """
    Map open interest → 0–100 using a log scale.
    OI = 0 → 0, OI = 10 000 → ~100. Log scale avoids mega-liquid tickers dominating.
    """
    if oi <= 0:
        return 0.0
    # log10(10000) ≈ 4; scale so OI=10000 → 100
    return _clamp(math.log10(oi + 1) / math.log10(10001) * 100)


def _norm_iv_rank(iv: float) -> float:
    """
    Map IV (as decimal, e.g. 0.35 = 35 %) → 0–100.
    Moderate IV (30–50 %) is ideal for CSPs: enough premium, not a panic event.
    Bell-curve-like: peaks at ~40 %, falls off toward 0 % and 100 %+ extremes.
    We use a triangle shape: 0 at 0, peak at 0.40, 0 at 1.0.
    """
    if iv <= 0:
        return 0.0
    peak = 0.40
    if iv <= peak:
        return _clamp(iv / peak * 100)
    else:
        # Decreasing after peak: IV=80 % scores 50, IV=100 % scores ~0
        return _clamp((1.0 - iv) / (1.0 - peak) * 100)


def _estimate_delta(otm_pct: float, iv: float, dte: int) -> float:
    """
    Quick delta approximation for a put using the N(d2) approximation.
    This is a rough estimate used only when yfinance does not provide greeks.

    For an OTM put: delta is between 0 and -0.5.
    We return the absolute value so higher = closer to ATM.
    """
    if iv <= 0 or dte <= 0:
        return 0.0
    # d2 = ln(S/K) / (sigma * sqrt(T)) — simplified (r=0, no dividends)
    # otm_pct is (stock_price - strike) / stock_price * 100 (positive when OTM)
    moneyness = otm_pct / 100.0  # ~ln(S/K) for small values
    sigma_sqrt_t = iv * math.sqrt(dte / 365.0)
    if sigma_sqrt_t == 0:
        return 0.0
    d2 = moneyness / sigma_sqrt_t
    # Approximate N(-d2) for put delta (absolute value)
    # Using logistic approximation of the normal CDF
    delta_abs = 1 / (1 + math.exp(1.7 * d2))
    return round(delta_abs, 4)


# ── Main public function ────────────────────────────────────────────────────

def get_csp_opportunities(
    ticker: str,
    min_premium_pct: float = 0.5,  # Minimum annualised return % to include
    max_delta: float = 0.35,         # Absolute delta upper bound
    min_dte: int = 7,
    max_dte: int = 45,
    min_score: float = 50.0,         # Minimum CSP Score
) -> list[dict[str, Any]]:
    """
    Fetch the full put options chain for `ticker` and return a sorted list of
    CSP opportunity dicts filtered by the supplied criteria.

    Returns an empty list (not an exception) on any data-fetch error so the UI
    can display a friendly message without crashing.
    """
    try:
        tk = yf.Ticker(ticker.upper())
        info = tk.fast_info  # lighter than .info, gives current_price quickly

        # Current stock price — use regularMarketPrice, fall back to previousClose
        try:
            stock_price = float(info.last_price or info.previous_close)
        except Exception:
            stock_price = None

        if not stock_price or stock_price <= 0:
            logger.warning("Could not determine stock price for %s", ticker)
            return []

        expirations = tk.options
        if not expirations:
            logger.warning("No options data available for %s", ticker)
            return []

        results: list[dict[str, Any]] = []

        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            dte = (exp_date - date.today()).days

            if dte < min_dte or dte > max_dte:
                continue

            try:
                chain = tk.option_chain(exp_str)
                puts: pd.DataFrame = chain.puts
            except Exception as e:
                logger.warning("Failed to fetch chain for %s %s: %s", ticker, exp_str, e)
                continue

            if puts.empty:
                continue

            for _, row in puts.iterrows():
                strike = float(row.get("strike", 0))
                if strike <= 0:
                    continue

                # Note: Allowing ITM puts (strike >= stock_price) per user request

                bid = float(row.get("bid", 0) or 0)
                ask = float(row.get("ask", 0) or 0)
                mid = round((bid + ask) / 2, 4) if ask > 0 else bid
                iv = float(row.get("impliedVolatility", 0) or 0)
                raw_vol = row.get("volume", 0)
                volume = int(raw_vol) if pd.notna(raw_vol) else 0

                raw_oi = row.get("openInterest", 0)
                open_interest = int(raw_oi) if pd.notna(raw_oi) else 0

                # % premium relative to strike (the cash we secure)
                premium_pct = (mid / strike * 100) if strike > 0 else 0
                annualised_return = (premium_pct * (365 / dte)) if dte > 0 else 0

                if annualised_return < min_premium_pct:
                    continue

                # % Out-of-the-money — positive means below current price (safer)
                otm_pct = ((stock_price - strike) / stock_price) * 100

                # Delta: use yfinance value if present, otherwise estimate
                raw_delta = row.get("delta", None)
                if raw_delta is not None and not pd.isna(raw_delta):
                    delta = abs(float(raw_delta))
                else:
                    delta = _estimate_delta(otm_pct, iv, dte)

                if delta > max_delta:
                    continue

                break_even = strike - mid

                # ── CSP Score computation ───────────────────────────────────
                ann_score = _norm_annualised(annualised_return)
                otm_score = _norm_otm(otm_pct)
                oi_score = _norm_open_interest(open_interest)
                iv_score = _norm_iv_rank(iv)

                csp_score = round(
                    ann_score * 0.4
                    + otm_score * 0.3
                    + oi_score * 0.2
                    + iv_score * 0.1,
                    1,
                )

                if csp_score < min_score:
                    continue

                results.append({
                    "ticker": ticker.upper(),
                    "expiration": exp_str,
                    "dte": dte,
                    "strike": strike,
                    "otm_pct": round(otm_pct, 2),
                    "bid": bid,
                    "ask": ask,
                    "mid": mid,
                    "premium_pct": round(premium_pct, 4),
                    "annualised_return": round(annualised_return, 2),
                    "delta": round(delta, 4),
                    "iv": round(iv * 100, 2),   # Store as % (e.g. 35.00 not 0.35)
                    "volume": volume,
                    "open_interest": open_interest,
                    "break_even": round(break_even, 4),
                    "stock_price": round(stock_price, 4),
                    "csp_score": csp_score,
                    # Score colour class for the template
                    "score_class": (
                        "score-green" if csp_score >= 70
                        else "score-yellow" if csp_score >= 50
                        else "score-red"
                    ),
                })

        # Sort by CSP Score descending so best opportunities appear first
        results.sort(key=lambda x: x["csp_score"], reverse=True)
        return results

    except Exception as e:
        logger.exception("Unexpected error fetching CSP opportunities for %s: %s", ticker, e)
        return []


def get_current_price(ticker: str) -> float | None:
    """Return the latest price for a ticker, or None on failure."""
    try:
        info = yf.Ticker(ticker.upper()).fast_info
        price = float(info.last_price or info.previous_close)
        return price if price > 0 else None
    except Exception:
        return None


def get_current_option_price(ticker: str, expiration: str, strike: float) -> float | None:
    """
    Attempt to find the current mid-price for a specific put contract.
    Used to mark open trades to market for unrealized P&L calculation.
    Returns None if the contract can no longer be found (e.g. already expired).
    """
    try:
        tk = yf.Ticker(ticker.upper())
        chain = tk.option_chain(expiration)
        puts = chain.puts
        match = puts[abs(puts["strike"] - strike) < 0.01]
        if match.empty:
            return None
        row = match.iloc[0]
        bid = float(row.get("bid", 0) or 0)
        ask = float(row.get("ask", 0) or 0)
        return round((bid + ask) / 2, 4) if ask > 0 else bid
    except Exception:
        return None
