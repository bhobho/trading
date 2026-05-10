from datetime import date
from models.trade import CSPTrade
from services.trade_service import get_portfolio_summary

# Mock trades
t1 = CSPTrade(ticker="AAPL", premium_received=1.5, num_contracts=1, open_date=date(2026, 4, 25), status="open")
t2 = CSPTrade(ticker="TSLA", premium_received=2.0, num_contracts=2, open_date=date(2026, 5, 5), status="open")

trades = [t1, t2]
summary = get_portfolio_summary(trades)

print(f"Total Premium: {summary['total_premium']}")
print(f"Month Premium: {summary['month_premium']}")
print(f"Today: {date.today()}")
