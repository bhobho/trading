import sqlite3
from datetime import date

conn = sqlite3.connect('csp_analyzer.db')
cursor = conn.cursor()

print("Checking trades in DB...")
cursor.execute("SELECT id, ticker, open_date, premium_received, num_contracts FROM csp_trades")
rows = cursor.fetchall()

today = date.today()
print(f"Today: {today}")

for row in rows:
    print(row)

conn.close()
