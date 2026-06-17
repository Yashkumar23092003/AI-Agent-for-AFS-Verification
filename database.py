"""
database.py — persistence layer.

Works on BOTH:
  • SQLite (local dev)          — default, file kyc_history.db
  • PostgreSQL (cloud / Neon)   — when DATABASE_URL env var is set

The public function signatures and return types are identical across both
backends, so no other module needs to change.
"""
import os
import json
import datetime
import pandas as pd
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, Text, insert, select, text,
)

# ── Engine selection ───────────────────────────────────────────────────────────
# Local default = SQLite file. In the cloud set DATABASE_URL to your Neon Postgres URL.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///kyc_history.db")

# Neon/Heroku hand out "postgres://…"; SQLAlchemy wants "postgresql://…".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    # Allow use across Streamlit's threads
    _connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
metadata = MetaData()

# ── Schema ──────────────────────────────────────────────────────────────────────
verifications = Table(
    "verifications", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Text),
    Column("buyer_name", Text),
    Column("project_name", Text),
    Column("unit_number", Text),
    Column("status", Text),
    Column("report_text", Text),
)

sheet_audits = Table(
    "sheet_audits", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Text),
    Column("unit_no", Text),
    Column("buyer_name", Text),
    Column("project_name", Text),
    Column("sheet_id", Text),
    Column("tab_name", Text),
    Column("verdict", Text),
    Column("per_field_json", Text),
    Column("afs_filename", Text),
)

full_verifications = Table(
    "full_verifications", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Text),
    Column("unit_no", Text),
    Column("buyer_name", Text),
    Column("project_name", Text),
    Column("afs_date", Text),
    Column("kyc_status", Text),
    Column("sheet_verdict", Text),
    Column("overall_verdict", Text),
    Column("kyc_report_text", Text),
    Column("sheet_per_field_json", Text),
    Column("afs_filename", Text),
    Column("sheet_id", Text),
    Column("tab_name", Text),
)


def init_db():
    """Creates all tables if they don't exist (works on SQLite and Postgres)."""
    metadata.create_all(engine)


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── verifications (KYC-only) ─────────────────────────────────────────────────────
def save_verification(buyer_name, project_name, unit_number, status, report_text):
    with engine.begin() as conn:
        conn.execute(insert(verifications).values(
            date=_now(), buyer_name=buyer_name, project_name=project_name,
            unit_number=unit_number, status=status, report_text=report_text,
        ))


def get_all_verifications_df():
    stmt = select(
        verifications.c.id, verifications.c.date, verifications.c.buyer_name,
        verifications.c.project_name, verifications.c.unit_number, verifications.c.status,
    ).order_by(verifications.c.id.desc())
    with engine.connect() as conn:
        return pd.read_sql_query(stmt, conn)


def get_report_by_id(record_id):
    stmt = select(verifications.c.report_text).where(verifications.c.id == record_id)
    with engine.connect() as conn:
        row = conn.execute(stmt).fetchone()
    return row[0] if row else "Report not found."


# ── shared field serialisation ───────────────────────────────────────────────────
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


# ── sheet_audits ──────────────────────────────────────────────────────────────────
def save_sheet_audit(unit_no, buyer_name, project_name, sheet_id, tab_name,
                     verdict, fields, afs_filename):
    with engine.begin() as conn:
        conn.execute(insert(sheet_audits).values(
            date=_now(), unit_no=unit_no, buyer_name=buyer_name,
            project_name=project_name, sheet_id=sheet_id, tab_name=tab_name,
            verdict=verdict, per_field_json=_serialise_fields(fields),
            afs_filename=afs_filename,
        ))


def get_all_sheet_audits_df():
    stmt = select(
        sheet_audits.c.id, sheet_audits.c.date, sheet_audits.c.unit_no,
        sheet_audits.c.buyer_name, sheet_audits.c.project_name, sheet_audits.c.verdict,
    ).order_by(sheet_audits.c.id.desc())
    with engine.connect() as conn:
        return pd.read_sql_query(stmt, conn)


def get_sheet_audit_by_id(record_id: int) -> dict:
    stmt = select(sheet_audits).where(sheet_audits.c.id == record_id)
    with engine.connect() as conn:
        row = conn.execute(stmt).mappings().fetchone()
    if not row:
        return {}
    record = dict(row)
    record["per_field_json"] = json.loads(record.get("per_field_json") or "[]")
    return record


# ── full_verifications ─────────────────────────────────────────────────────────────
def save_full_verification(
    unit_no, buyer_name, project_name, afs_date,
    kyc_status, sheet_verdict, overall_verdict,
    kyc_report_text, sheet_fields, afs_filename,
    sheet_id, tab_name,
):
    with engine.begin() as conn:
        conn.execute(insert(full_verifications).values(
            date=_now(), unit_no=unit_no, buyer_name=buyer_name,
            project_name=project_name, afs_date=afs_date, kyc_status=kyc_status,
            sheet_verdict=sheet_verdict, overall_verdict=overall_verdict,
            kyc_report_text=kyc_report_text,
            sheet_per_field_json=_serialise_fields(sheet_fields),
            afs_filename=afs_filename, sheet_id=sheet_id, tab_name=tab_name,
        ))


def get_all_full_verifications_df():
    stmt = select(
        full_verifications.c.id, full_verifications.c.date, full_verifications.c.unit_no,
        full_verifications.c.buyer_name, full_verifications.c.project_name,
        full_verifications.c.kyc_status, full_verifications.c.sheet_verdict,
        full_verifications.c.overall_verdict,
    ).order_by(full_verifications.c.id.desc())
    with engine.connect() as conn:
        return pd.read_sql_query(stmt, conn)


def get_full_verification_by_id(record_id: int) -> dict:
    stmt = select(full_verifications).where(full_verifications.c.id == record_id)
    with engine.connect() as conn:
        row = conn.execute(stmt).mappings().fetchone()
    if not row:
        return {}
    record = dict(row)
    record["sheet_per_field_json"] = json.loads(record.get("sheet_per_field_json") or "[]")
    return record
