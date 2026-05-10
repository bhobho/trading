"""
models/trade.py — SQLAlchemy ORM model for Cash-Secured Put trades.

Computed / derived fields (current_stock_price, unrealized_pnl, etc.) are NOT
stored here — they are calculated at query time by trade_service.py so they
always reflect live data.
"""
from datetime import datetime, date
from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from database import Base


class CSPTrade(Base):
    __tablename__ = "csp_trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Option contract details
    ticker = Column(String(16), nullable=False, index=True)
    strike_price = Column(Float, nullable=False)          # Per-share strike
    expiration_date = Column(Date, nullable=False)
    num_contracts = Column(Integer, nullable=False, default=1)

    # Premium is stored as per-share (multiply by 100 for per-contract dollar value)
    premium_received = Column(Float, nullable=False)      # Mid price when trade opened

    # Trade lifecycle dates
    open_date = Column(Date, nullable=False, default=date.today)
    close_date = Column(Date, nullable=True)              # None if still open

    # Status: "open" | "closed" | "assigned" | "expired"
    status = Column(String(16), nullable=False, default="open", index=True)

    # If closed early, the premium paid to buy back the option (per share)
    close_premium = Column(Float, nullable=True)

    # Optional metrics when trade opened
    collateral = Column(Float, nullable=True)
    delta = Column(Float, nullable=True)
    iv = Column(Float, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # ── Computed properties (no DB columns) ────────────────────────────────────

    @property
    def total_premium(self) -> float:
        """Total dollars collected when opening the trade (per-share × 100 × contracts)."""
        return self.premium_received * 100 * self.num_contracts

    @property
    def max_profit(self) -> float:
        """Maximum profit = total premium collected (achieved if option expires worthless)."""
        return self.total_premium

    @property
    def days_to_expiry(self) -> int:
        """Calendar days from today to expiration (negative if expired)."""
        return (self.expiration_date - date.today()).days

    @property
    def days_held(self) -> int:
        """Calendar days since the trade was opened."""
        end = self.close_date or date.today()
        return (end - self.open_date).days

    @property
    def return_pct(self) -> float:
        """Simple return % = premium / strike * 100."""
        if self.strike_price == 0:
            return 0.0
        return (self.premium_received / self.strike_price) * 100

    @property
    def annualized_return(self) -> float:
        """
        Annualized return % using the total DTE of the trade.
        Uses days_held for closed trades so we don't divide by zero for same-day closes.
        """
        total_days = (self.expiration_date - self.open_date).days
        if total_days <= 0:
            total_days = 1
        return self.return_pct * (365 / total_days)

    @property
    def realized_pnl(self) -> float | None:
        """
        Realized P&L for closed/expired/assigned trades.
        - expired / assigned with no close_premium: full premium kept.
        - closed early: (premium_received - close_premium) * 100 * contracts
        """
        if self.status == "open":
            return None
        if self.status in ("expired",):
            return self.total_premium
        if self.status == "assigned":
            # Assignment means stock was put to us; P&L is just the premium (stock position is separate)
            return self.total_premium
        if self.status == "closed" and self.close_premium is not None:
            return (self.premium_received - self.close_premium) * 100 * self.num_contracts
        return self.total_premium
