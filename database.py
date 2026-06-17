import sqlite3
import datetime
import json
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
        conn.execute('''CREATE TABLE IF NOT EXISTS sheet_audits
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      unit_no TEXT,
                      buyer_name TEXT,
                      project_name TEXT,
                      sheet_id TEXT,
                      tab_name TEXT,
                      verdict TEXT,
                      per_field_json TEXT,
                      afs_filename TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS full_verifications
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      unit_no TEXT,
                      buyer_name TEXT,
                      project_name TEXT,
                      afs_date TEXT,
                      kyc_status TEXT,
                      sheet_verdict TEXT,
                      overall_verdict TEXT,
                      kyc_report_text TEXT,
                      sheet_per_field_json TEXT,
                      afs_filename TEXT,
                      sheet_id TEXT,
                      tab_name TEXT)''')
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


# ── Sheet audit table ─────────────────────────────────────────────────────────

def save_sheet_audit(unit_no, buyer_name, project_name, sheet_id, tab_name,
                     verdict, fields, afs_filename):
    """Serialises FieldResult list to JSON and saves the audit record."""
    per_field = [
        {
            "field_name": f.field_name,
            "status": f.status,
            "afs_distinct_values": f.afs_distinct_values,
            "sheet_raw": f.sheet_raw,
            "afs_normalized": f.afs_normalized,
            "sheet_normalized": f.sheet_normalized,
            "detail": f.detail,
        }
        for f in fields
    ]
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO sheet_audits "
            "(date, unit_no, buyer_name, project_name, sheet_id, tab_name, "
            "verdict, per_field_json, afs_filename) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (date_str, unit_no, buyer_name, project_name, sheet_id, tab_name,
             verdict, json.dumps(per_field), afs_filename),
        )
        conn.commit()


def get_all_sheet_audits_df():
    """Returns all sheet audit records as a DataFrame (no per_field_json)."""
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query(
            "SELECT id, date, unit_no, buyer_name, project_name, verdict "
            "FROM sheet_audits ORDER BY id DESC",
            conn,
        )
    return df


def get_sheet_audit_by_id(record_id: int) -> dict:
    """Returns the full audit record including parsed per_field_json."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT * FROM sheet_audits WHERE id=?", (record_id,)
        )
        row = cursor.fetchone()
        if not row:
            return {}
        cols = [d[0] for d in cursor.description]
    record = dict(zip(cols, row))
    record["per_field_json"] = json.loads(record.get("per_field_json") or "[]")
    return record


# ── Full verification table ───────────────────────────────────────────────────

def _serialise_fields(fields) -> str:
    per_field = []
    for f in fields:
        if isinstance(f, dict):
            per_field.append(f)
        else:
            per_field.append({
                "field_name": f.field_name,
                "status": f.status,
                "afs_distinct_values": f.afs_distinct_values,
                "sheet_raw": f.sheet_raw,
                "afs_normalized": f.afs_normalized,
                "sheet_normalized": f.sheet_normalized,
                "detail": f.detail,
            })
    return json.dumps(per_field)


def save_full_verification(
    unit_no, buyer_name, project_name, afs_date,
    kyc_status, sheet_verdict, overall_verdict,
    kyc_report_text, sheet_fields, afs_filename,
    sheet_id, tab_name,
):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO full_verifications "
            "(date, unit_no, buyer_name, project_name, afs_date, kyc_status, "
            "sheet_verdict, overall_verdict, kyc_report_text, sheet_per_field_json, "
            "afs_filename, sheet_id, tab_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (date_str, unit_no, buyer_name, project_name, afs_date,
             kyc_status, sheet_verdict, overall_verdict, kyc_report_text,
             _serialise_fields(sheet_fields), afs_filename, sheet_id, tab_name),
        )
        conn.commit()


def get_all_full_verifications_df():
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query(
            "SELECT id, date, unit_no, buyer_name, project_name, "
            "kyc_status, sheet_verdict, overall_verdict "
            "FROM full_verifications ORDER BY id DESC",
            conn,
        )
    return df


def get_full_verification_by_id(record_id: int) -> dict:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute(
            "SELECT * FROM full_verifications WHERE id=?", (record_id,)
        )
        row = cursor.fetchone()
        if not row:
            return {}
        cols = [d[0] for d in cursor.description]
    record = dict(zip(cols, row))
    record["sheet_per_field_json"] = json.loads(record.get("sheet_per_field_json") or "[]")
    return record
