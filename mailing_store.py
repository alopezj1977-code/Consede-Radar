"""Workspace-scoped Mailing persistence on Neon PostgreSQL or local SQLite.

This module owns only its mailing_* tables and does not initialize or mutate
Radar tables or the CONCEDE V3 scoring schema.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


MAILING_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS mailing_contacts (
        contact_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        company TEXT NOT NULL,
        email TEXT NOT NULL,
        contact_name TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT '',
        authorized INTEGER NOT NULL DEFAULT 0,
        email_valid INTEGER NOT NULL DEFAULT 0,
        campaign_eligible INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(workspace_id, email)
    )""",
    """CREATE INDEX IF NOT EXISTS ix_mailing_contacts_workspace
       ON mailing_contacts(workspace_id, campaign_eligible)""",
    """CREATE TABLE IF NOT EXISTS mailing_campaigns (
        campaign_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        campaign_name TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        recipients_json TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        accepted_at TEXT
    )""",
    """CREATE INDEX IF NOT EXISTS ix_mailing_campaigns_workspace
       ON mailing_campaigns(workspace_id, status, updated_at)""",
)


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect(db_path=None):
    database_url = os.getenv("DATABASE_URL", "").strip()
    con = None
    postgres = bool(database_url)
    try:
        if postgres:
            import psycopg
            from psycopg.rows import dict_row
            con = psycopg.connect(
                database_url,
                row_factory=dict_row,
                connect_timeout=10,
                sslmode="require",
            )
        else:
            path = Path(db_path or "data/concede_radar.sqlite3")
            path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(str(path))
            con.row_factory = sqlite3.Row
        yield con, postgres
        con.commit()
    except Exception:
        if con is not None:
            con.rollback()
        raise
    finally:
        if con is not None:
            con.close()


def _sql(statement, postgres):
    return statement.replace("?", "%s") if postgres else statement


def ensure_schema(db_path=None):
    with _connect(db_path) as (con, postgres):
        for statement in MAILING_SCHEMA:
            con.execute(_sql(statement, postgres))


def upsert_contacts(workspace_id, contacts, db_path=None):
    workspace = str(workspace_id or "").strip()
    if not workspace:
        raise ValueError("workspace_id es obligatorio.")
    now = _now()
    saved = 0
    statement = """INSERT INTO mailing_contacts(
        contact_id, workspace_id, company, email, contact_name, source,
        authorized, email_valid, campaign_eligible, created_at, updated_at
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(workspace_id, email) DO UPDATE SET
        company=excluded.company,
        contact_name=excluded.contact_name,
        source=excluded.source,
        authorized=excluded.authorized,
        email_valid=excluded.email_valid,
        campaign_eligible=excluded.campaign_eligible,
        updated_at=excluded.updated_at"""
    with _connect(db_path) as (con, postgres):
        for contact in contacts:
            email = str(contact.get("correo", "")).strip().lower()
            if not email:
                continue
            con.execute(
                _sql(statement, postgres),
                (
                    str(uuid.uuid4()), workspace,
                    str(contact.get("empresa", "")).strip(), email,
                    str(contact.get("contacto", "")).strip(),
                    str(contact.get("fuente", "")).strip(),
                    int(bool(contact.get("autorizado", False))),
                    int(bool(contact.get("correo_valido", False))),
                    int(bool(contact.get("apto", False))),
                    now, now,
                ),
            )
            saved += 1
    return saved


def list_contacts(workspace_id, db_path=None):
    with _connect(db_path) as (con, postgres):
        rows = con.execute(
            _sql(
                """SELECT company AS empresa, email AS correo,
                          contact_name AS contacto, source AS fuente,
                          authorized, email_valid, campaign_eligible
                   FROM mailing_contacts
                   WHERE workspace_id=?
                   ORDER BY company, email""",
                postgres,
            ),
            (str(workspace_id),),
        ).fetchall()
    return [
        {
            "empresa": row["empresa"],
            "correo": row["correo"],
            "contacto": row["contacto"],
            "fuente": row["fuente"],
            "autorizado": bool(row["authorized"]),
            "correo_valido": bool(row["email_valid"]),
            "apto": bool(row["campaign_eligible"]),
        }
        for row in rows
    ]


def save_draft(workspace_id, draft, db_path=None):
    workspace = str(workspace_id or "").strip()
    if not workspace:
        raise ValueError("workspace_id es obligatorio.")
    now = _now()
    campaign_id = str(draft.get("id") or uuid.uuid4())
    statement = """INSERT INTO mailing_campaigns(
        campaign_id, workspace_id, campaign_name, subject, body,
        recipients_json, status, created_at, updated_at, accepted_at
    ) VALUES(?,?,?,?,?,?,?,?,?,NULL)
    ON CONFLICT(campaign_id) DO UPDATE SET
        campaign_name=excluded.campaign_name,
        subject=excluded.subject,
        body=excluded.body,
        recipients_json=excluded.recipients_json,
        status='DRAFT',
        updated_at=excluded.updated_at,
        accepted_at=NULL
    WHERE mailing_campaigns.workspace_id=excluded.workspace_id"""
    with _connect(db_path) as (con, postgres):
        con.execute(
            _sql(statement, postgres),
            (
                campaign_id, workspace, str(draft.get("name", "")).strip(),
                str(draft.get("subject", "")).strip(),
                str(draft.get("body", "")).strip(),
                json.dumps(list(draft.get("recipients", [])), ensure_ascii=False),
                "DRAFT", now, now,
            ),
        )
    return campaign_id


def get_latest_draft(workspace_id, db_path=None):
    with _connect(db_path) as (con, postgres):
        row = con.execute(
            _sql(
                """SELECT campaign_id, campaign_name, subject, body, recipients_json
                   FROM mailing_campaigns
                   WHERE workspace_id=? AND status='DRAFT'
                   ORDER BY updated_at DESC LIMIT 1""",
                postgres,
            ),
            (str(workspace_id),),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["campaign_id"],
        "name": row["campaign_name"],
        "subject": row["subject"],
        "body": row["body"],
        "recipients": json.loads(row["recipients_json"]),
    }


def mark_accepted(workspace_id, campaign_id, db_path=None):
    now = _now()
    with _connect(db_path) as (con, postgres):
        cur = con.execute(
            _sql(
                """UPDATE mailing_campaigns
                   SET status='ACCEPTED_BY_GRAPH', accepted_at=?, updated_at=?
                   WHERE workspace_id=? AND campaign_id=? AND status='DRAFT'""",
                postgres,
            ),
            (now, now, str(workspace_id), str(campaign_id)),
        )
        if cur.rowcount != 1:
            raise ValueError(
                "El borrador no existe en este workspace o ya fue procesado."
            )

def validate_campaign_recipients(workspace_id, recipients, db_path=None):
    """Return recipients still authorized and eligible at the exact time of sending."""
    requested = list(dict.fromkeys(
        str(email).strip().lower() for email in recipients if str(email).strip()
    ))
    if not requested:
        return [], []
    placeholders = ",".join("?" for _ in requested)
    statement = (
        "SELECT email FROM mailing_contacts "
        "WHERE workspace_id=? AND campaign_eligible=1 "
        f"AND email IN ({placeholders})"
    )
    with _connect(db_path) as (con, postgres):
        rows = con.execute(
            _sql(statement, postgres), (str(workspace_id), *requested)
        ).fetchall()
    eligible = {row["email"] for row in rows}
    allowed = [email for email in requested if email in eligible]
    blocked = [email for email in requested if email not in eligible]
    return allowed, blocked
