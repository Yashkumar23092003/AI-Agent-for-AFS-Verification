import sqlite3
import datetime
import pandas as pd

DB_FILE = 'kyc_history.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS verifications
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      buyer_name TEXT,
                      project_name TEXT,
                      unit_number TEXT,
                      status TEXT,
                      report_text TEXT)''')
        conn.commit()

def save_verification(buyer_name, project_name, unit_number, status, report_text):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO verifications (date, buyer_name, project_name, unit_number, status, report_text) VALUES (?, ?, ?, ?, ?, ?)",
                  (date_str, buyer_name, project_name, unit_number, status, report_text))
        conn.commit()

def get_all_verifications_df():
    """Returns all verifications as a pandas DataFrame for easy display in Streamlit."""
    with sqlite3.connect(DB_FILE) as conn:
        query = "SELECT id, date, buyer_name, project_name, unit_number, status FROM verifications ORDER BY id DESC"
        df = pd.read_sql_query(query, conn)
    return df

def get_report_by_id(record_id):
    """Fetches the full report text for a specific verification ID."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT report_text FROM verifications WHERE id=?", (record_id,))
        row = cursor.fetchone()
    return row[0] if row else "Report not found."
