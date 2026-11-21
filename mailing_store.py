"""Shared persistence for CONCEDE Mailing contacts and campaign drafts.

Uses the same Neon/SQLite connection policy as Radar, but stores Mailing data
in dedicated tables and scopes every query by workspace_id.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from radar_store import connect


MAILING_SCHEMA = """
CREATE TABLE IF NOT EXISTS mailing_contacts (
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
);
CREATE INDEX IF NOT EXISTS ix_mailing_contacts_workspace
    ON mailing_contacts(workspace_id, campaign_eligible);
CREATE TABLE IF NOT EXISTS mailing_campaigns (
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
);
CREATE INDEX IF NOT EXISTS ix_mailing_campaigns_workspace
    ON mailing_campaigns(workspace_id, status, updated_at);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(db_path=None):
    with connect(db_path) as con:
        for statement in MAILING_SCHEMA.split(";"):
            statement = statement.strip()
            if statement:
                con.execute(statement)


def upsert_contacts(workspace_id, contacts, db_path=None):
    workspace = str(workspace_id or "").strip()
    if not workspace:
        raise ValueError("workspace_id es obligatorio.")
    now = _now()
    saved = 0
    with connect(db_path) as con:
        for contact in contacts:
            email = str(contact.get("correo", "")).strip().lower()
            if not email:
                continue
            con.execute(
                """INSERT INTO mailing_contacts(
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
                    updated_at=excluded.updated_at""",
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
    with connect(db_path) as con:
        rows = con.execute(
            """SELECT company AS empresa, email AS correo,
                      contact_name AS contacto, source AS fuente,
                      authorized, email_valid, campaign_eligible
               FROM mailing_contacts
               WHERE workspace_id=?
               ORDER BY company, email""",
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
    with connect(db_path) as con:
        con.execute(
            """INSERT INTO mailing_campaigns(
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
            WHERE mailing_campaigns.workspace_id=excluded.workspace_id""",
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
    with connect(db_path) as con:
        row = con.execute(
            """SELECT campaign_id, campaign_name, subject, body, recipients_json
               FROM mailing_campaigns
               WHERE workspace_id=? AND status='DRAFT'
               ORDER BY updated_at DESC LIMIT 1""",
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
    with connect(db_path) as con:
        cur = con.execute(
            """UPDATE mailing_campaigns
               SET status='ACCEPTED_BY_GRAPH', accepted_at=?, updated_at=?
               WHERE workspace_id=? AND campaign_id=? AND status='DRAFT'""",
            (_now(), _now(), str(workspace_id), str(campaign_id)),
        )
        if cur.rowcount != 1:
            raise ValueError("El borrador no existe en este workspace o ya fue procesado.")
