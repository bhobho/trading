"""
services/trade_service.py — Business logic for CSP trade P&L and summary statistics.

All "live" computed fields (current price, unrealized P&L) are derived here so
the database model stays clean and the data is always fresh.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from models.trade import CSPTrade
from services.options_service import get_current_price, get_current_option_price


def enrich_trade(trade: CSPTrade) -> dict[str, Any]:
    """
    Convert a CSPTrade ORM object to a dictionary that includes all computed
    fields needed by the templates. Live price data is fetched here.
    """
    current_stock_price = get_current_price(trade.ticker)

    # For open trades, fetch the current option mid to compute unrealized P&L.
    # For closed/expired trades, use the stored close_premium (or zero if expired).
    current_option_price: float | None = None
    unrealized_pnl: float | None = None

    if trade.status == "open":
        exp_str = trade.expiration_date.strftime("%Y-%m-%d")
        current_option_price = get_current_option_price(
            trade.ticker, exp_str, trade.strike_price
        )
        if current_option_price is not None:
            # P&L = premium sold − current option price (positive if option lost value)
            unrealized_pnl = round(
                (trade.premium_received - current_option_price) * 100 * trade.num_contracts, 2
            )

    return {
        "id": trade.id,
        "ticker": trade.ticker,
        "strike_price": trade.strike_price,
        "expiration_date": trade.expiration_date.isoformat(),
        "dte": trade.days_to_expiry,
        "num_contracts": trade.num_contracts,
        "premium_received": trade.premium_received,
        "total_premium": round(trade.total_premium, 2),
        "open_date": trade.open_date.isoformat(),
        "close_date": trade.close_date.isoformat() if trade.close_date else None,
        "status": trade.status,
        "close_premium": trade.close_premium,
        "notes": trade.notes or "",
        "return_pct": round(trade.return_pct, 2),
        "annualized_return": round(trade.annualized_return, 2),
        "realized_pnl": trade.realized_pnl,
        "current_stock_price": current_stock_price,
        "current_option_price": current_option_price,
        "unrealized_pnl": unrealized_pnl,
    }


def enrich_trades_batch(trades: list[CSPTrade]) -> list[dict[str, Any]]:
    """Enrich a list of trades. Wraps enrich_trade in a loop."""
    return [enrich_trade(t) for t in trades]


def get_portfolio_summary(trades: list[CSPTrade]) -> dict[str, Any]:
    """
    Compute aggregate statistics shown on the dashboard.
    Accepts a list of CSPTrade ORM objects (all trades for the current user).
    """
    today = date.today()
    current_month = today.month
    current_year = today.year

    open_trades = [t for t in trades if t.status == "open"]
    closed_trades = [t for t in trades if t.status in ("closed", "expired", "assigned")]

    total_premium = sum(t.total_premium for t in trades)
    month_premium = sum(
        t.total_premium for t in trades
        if t.open_date.month == current_month and t.open_date.year == current_year
    )

    # Win = closed with profit (realized P&L > 0)
    wins = [t for t in closed_trades if (t.realized_pnl or 0) > 0]
    win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0.0

    # Average annualised return across all closed trades
    ann_returns = [t.annualized_return for t in closed_trades if t.annualized_return > 0]
    avg_ann_return = sum(ann_returns) / len(ann_returns) if ann_returns else 0.0

    # Upcoming expirations in next 14 days (open only)
    upcoming = [t for t in open_trades if 0 <= t.days_to_expiry <= 14]
    upcoming.sort(key=lambda t: t.days_to_expiry)

    # Monthly premium chart data: last 12 months
    monthly: dict[str, float] = {}
    for t in trades:
        key = t.open_date.strftime("%b %Y")
        monthly[key] = monthly.get(key, 0) + t.total_premium

    return {
        "total_open": len(open_trades),
        "total_premium": round(total_premium, 2),
        "month_premium": round(month_premium, 2),
        "win_rate": round(win_rate, 1),
        "total_trades": len(trades),
        "avg_ann_return": round(avg_ann_return, 2),
        "upcoming_expirations": upcoming,
        "monthly_premium": monthly,
    }


def get_journal_summary(trades: list[CSPTrade]) -> dict[str, Any]:
    """Summary stats shown at the top of the trade journal page."""
    total_premium = sum(t.total_premium for t in trades)
    closed = [t for t in trades if t.status in ("closed", "expired", "assigned")]
    wins = [t for t in closed if (t.realized_pnl or 0) > 0]
    win_rate = (len(wins) / len(closed) * 100) if closed else 0.0

    ann_returns = [t.annualized_return for t in trades if t.annualized_return > 0]
    avg_ann = sum(ann_returns) / len(ann_returns) if ann_returns else 0.0

    return {
        "total_trades": len(trades),
        "total_premium": round(total_premium, 2),
        "win_rate": round(win_rate, 1),
        "avg_ann_return": round(avg_ann, 2),
    }
