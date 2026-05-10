import sqlite3
import os

db_path = "csp_analyzer.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Add is_verified column
        cursor.execute("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0 NOT NULL")
        print("Added is_verified column.")
    except sqlite3.OperationalError:
        print("is_verified column already exists.")

    try:
        # Add verification_token column
        cursor.execute("ALTER TABLE users ADD COLUMN verification_token VARCHAR(255)")
        print("Added verification_token column.")
    except sqlite3.OperationalError:
        print("verification_token column already exists.")
    
    # Mark existing users as verified
    cursor.execute("UPDATE users SET is_verified = 1")
    print("Marked existing users as verified.")
    
    conn.commit()
    conn.close()
else:
    print(f"Database {db_path} not found. Re-run app to create it.")
