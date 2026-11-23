"""Workspace-scoped commercial CRM evidence. This module never changes V3 scores."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

CRM_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS crm_accounts (
        account_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        denue_id TEXT NOT NULL,
        company_name TEXT NOT NULL,
        stage TEXT NOT NULL,
        owner TEXT NOT NULL,
        contact_name TEXT NOT NULL DEFAULT '',
        contact_email TEXT NOT NULL DEFAULT '',
        interest_confirmed INTEGER NOT NULL DEFAULT 0,
        need_evidence TEXT NOT NULL DEFAULT '',
        evidence_source TEXT NOT NULL DEFAULT '',
        next_action TEXT NOT NULL DEFAULT '',
        next_action_date TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(workspace_id, denue_id)
    )""",
    """CREATE INDEX IF NOT EXISTS ix_crm_accounts_workspace_stage
       ON crm_accounts(workspace_id, stage, updated_at)""",
    """CREATE TABLE IF NOT EXISTS crm_events (
        event_id TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        account_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        old_stage TEXT,
        new_stage TEXT,
        detail TEXT NOT NULL,
        actor TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS ix_crm_events_account
       ON crm_events(workspace_id, account_id, created_at)""",
)

STAGES = (
    "PROSPECTO",
    "CONTACTO",
    "INTERÉS",
    "CITA/OPORTUNIDAD",
    "PROPUESTA",
    "GANADA/PERDIDA",
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
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError("DATABASE_URL está configurada, pero falta psycopg[binary].") from exc
            con = psycopg.connect(database_url, row_factory=dict_row, connect_timeout=10, sslmode="require")
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
        for statement in CRM_SCHEMA:
            con.execute(statement)


def upsert_account(workspace_id, *, denue_id, company_name, stage="PROSPECTO",
                   owner, contact_name="", contact_email="", interest_confirmed=False,
                   need_evidence="", evidence_source="", next_action="", next_action_date="",
                   actor, db_path=None):
    workspace = str(workspace_id or "").strip()
    denue = str(denue_id or "").strip()
    name = str(company_name or "").strip()
    responsible = str(owner or "").strip()
    actor = str(actor or "").strip()
    if not workspace or not denue or not name or not responsible or not actor:
        raise ValueError("Workspace, ID DENUE, empresa, responsable y actor son obligatorios.")
    if stage not in STAGES:
        raise ValueError("Etapa CRM no reconocida.")
    if interest_confirmed and (not str(need_evidence).strip() or not str(evidence_source).strip()):
        raise ValueError("El interés confirmado requiere evidencia de necesidad y fuente documentada.")
    now = _now()
    with _connect(db_path) as (con, postgres):
        existing = con.execute(
            _sql("SELECT account_id, stage FROM crm_accounts WHERE workspace_id=? AND denue_id=?", postgres),
            (workspace, denue),
        ).fetchone()
        if existing:
            account_id = existing["account_id"]
            old_stage = existing["stage"]
            con.execute(_sql("""UPDATE crm_accounts SET company_name=?, stage=?, owner=?,
                contact_name=?, contact_email=?, interest_confirmed=?, need_evidence=?,
                evidence_source=?, next_action=?, next_action_date=?, updated_at=?
                WHERE workspace_id=? AND account_id=?""", postgres),
                (name, stage, responsible, str(contact_name).strip(), str(contact_email).strip().lower(),
                 int(bool(interest_confirmed)), str(need_evidence).strip(), str(evidence_source).strip(),
                 str(next_action).strip(), str(next_action_date).strip(), now, workspace, account_id))
        else:
            account_id = str(uuid.uuid4())
            old_stage = None
            con.execute(_sql("""INSERT INTO crm_accounts(
                account_id,workspace_id,denue_id,company_name,stage,owner,contact_name,contact_email,
                interest_confirmed,need_evidence,evidence_source,next_action,next_action_date,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", postgres),
                (account_id, workspace, denue, name, stage, responsible, str(contact_name).strip(),
                 str(contact_email).strip().lower(), int(bool(interest_confirmed)), str(need_evidence).strip(),
                 str(evidence_source).strip(), str(next_action).strip(), str(next_action_date).strip(), now, now))
        if old_stage != stage:
            con.execute(_sql("""INSERT INTO crm_events(
                event_id,workspace_id,account_id,event_type,old_stage,new_stage,detail,actor,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)""", postgres),
                (str(uuid.uuid4()), workspace, account_id, "STAGE_CHANGE", old_stage, stage,
                 "Cambio de etapa registrado desde CRM.", actor, now))
        con.execute(_sql("""INSERT INTO crm_events(
            event_id,workspace_id,account_id,event_type,old_stage,new_stage,detail,actor,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""", postgres),
            (str(uuid.uuid4()), workspace, account_id, "ACCOUNT_UPDATE", old_stage, stage,
             json.dumps({"interest_confirmed": bool(interest_confirmed), "has_need_evidence": bool(str(need_evidence).strip()),
                         "has_evidence_source": bool(str(evidence_source).strip())}, ensure_ascii=False),
             actor, now))
    return account_id


def list_accounts(workspace_id, db_path=None):
    with _connect(db_path) as (con, postgres):
        rows = con.execute(_sql("""SELECT denue_id, company_name, stage, owner, contact_name,
            contact_email, interest_confirmed, need_evidence, evidence_source, next_action,
            next_action_date, updated_at FROM crm_accounts WHERE workspace_id=?
            ORDER BY updated_at DESC""", postgres), (str(workspace_id),)).fetchall()
    return [dict(row) for row in rows]


def list_events(workspace_id, denue_id, db_path=None):
    with _connect(db_path) as (con, postgres):
        rows = con.execute(_sql("""SELECT e.event_type,e.old_stage,e.new_stage,e.detail,e.actor,e.created_at
            FROM crm_events e JOIN crm_accounts a ON a.account_id=e.account_id
            WHERE e.workspace_id=? AND a.workspace_id=? AND a.denue_id=?
            ORDER BY e.created_at DESC""", postgres),
            (str(workspace_id), str(workspace_id), str(denue_id))).fetchall()
    return [dict(row) for row in rows]
