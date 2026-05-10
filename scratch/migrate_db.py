import sqlite3
import os

db_path = "csp_analyzer.db"

if not os.path.exists(db_path):
    print(f"Database {db_path} not found. Skipping migration.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Adding collateral column...")
        cursor.execute("ALTER TABLE csp_trades ADD COLUMN collateral FLOAT")
    except sqlite3.OperationalError:
        print("Column collateral already exists.")
        
    try:
        print("Adding delta column...")
        cursor.execute("ALTER TABLE csp_trades ADD COLUMN delta FLOAT")
    except sqlite3.OperationalError:
        print("Column delta already exists.")
        
    try:
        print("Adding iv column...")
        cursor.execute("ALTER TABLE csp_trades ADD COLUMN iv FLOAT")
    except sqlite3.OperationalError:
        print("Column iv already exists.")
        
    conn.commit()
    conn.close()
    print("Migration completed successfully.")
