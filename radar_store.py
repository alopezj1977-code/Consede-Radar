"""CONCEDE AAA RADAR - persistent evidence store.
Radar evidence is isolated from the V3 scoring engine; signals never affect score.
Uses Neon PostgreSQL when DATABASE_URL is configured, otherwise local SQLite.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS companies (
  company_id TEXT PRIMARY KEY,
  denue_id TEXT,
  display_name TEXT NOT NULL,
  state_code TEXT,
  municipality TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signals (
  signal_id TEXT PRIMARY KEY,
  company_id TEXT,
  source_id TEXT NOT NULL,
  source_url TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  title TEXT NOT NULL,
  snippet TEXT,
  published_at TEXT,
  captured_at TEXT NOT NULL,
  source_status TEXT NOT NULL,
  identity_status TEXT NOT NULL,
  need_hypothesis TEXT,
  next_best_question TEXT,
  competition_status TEXT NOT NULL,
  human_review_status TEXT NOT NULL,
  reviewer TEXT,
  reviewed_at TEXT,
  review_reason TEXT,
  run_id TEXT NOT NULL,
  rule_version TEXT NOT NULL,
  score_impact REAL NOT NULL DEFAULT 0,
  payload_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_signals_company ON signals(company_id);
CREATE INDEX IF NOT EXISTS ix_signals_source ON signals(source_id, source_url);
"""

SIGNAL_TYPES = {
    "INV-EXPANSION", "VACANTE", "PERMISO-LICENCIA",
    "NOTICIA-CORPORATIVA", "LICITACION-CONTRATO", "PERFIL-DENUE"
}
COMPETITION = {"CLIENTE_POTENCIAL", "POSIBLE_COMPETIDOR", "MIXTO", "INDETERMINADO"}
REVIEW = {"PENDIENTE", "VALIDADA_COMERCIAL", "DESCARTADA", "NO_CONCLUYENTE"}
SOURCE_STATUS = {"LOCALIZADA", "ACCESIBLE", "INSPECCIONADA", "AUTOMATIZABLE", "FALLIDA"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class _HybridRow(dict):
    """Mapping row that also supports SQLite-style numeric indexing."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def _hybrid_row(cursor):
    names = [column.name for column in cursor.description]
    def make_row(values):
        return _HybridRow(zip(names, values))
    return make_row


class _PostgresConnection:
    """Small compatibility adapter for the SQLite-style queries used by Radar."""
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=None):
        # Existing Radar SQL uses qmark placeholders for SQLite.
        sql = re.sub(r"\?", "%s", sql)
        cur = self._connection.cursor()
        cur.execute(sql, params or ())
        return cur

    def executescript(self, script):
        for statement in script.split(";"):
            statement = statement.strip()
            if not statement or statement.upper().startswith("PRAGMA"):
                continue
            self.execute(statement)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


@contextmanager
def connect(db_path=None):
    """Open Neon PostgreSQL if DATABASE_URL is set; otherwise use SQLite locally."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    con = None
    try:
        if database_url:
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError(
                    "DATABASE_URL está configurada, pero falta psycopg[binary] en requirements.txt."
                ) from exc
            con = _PostgresConnection(
                psycopg.connect(
                    database_url,
                    row_factory=_hybrid_row,
                    connect_timeout=10,
                    sslmode="require",
                )
            )
            con.executescript(SCHEMA)
        else:
            path = Path(db_path or "data/concede_radar.sqlite3")
            path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(str(path))
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys = ON")
            con.executescript(SCHEMA)
        yield con
        con.commit()
    except Exception:
        if con is not None:
            con.rollback()
        raise
    finally:
        if con is not None:
            con.close()


def create_company(db_path, display_name, denue_id=None, state_code=None, municipality=None, company_id=None):
    if not str(display_name or "").strip():
        raise ValueError("display_name es obligatorio; razón social no lo es.")
    cid = company_id or str(uuid.uuid4())
    with connect(db_path) as con:
        con.execute("""INSERT INTO companies(company_id,denue_id,display_name,state_code,municipality,created_at)
        VALUES(?,?,?,?,?,?)""", (cid, denue_id, display_name.strip(), state_code, municipality, now_iso()))
    return cid


def add_signal(db_path, *, company_id=None, source_id, source_url, signal_type, title,
               snippet="", published_at=None, source_status="INSPECCIONADA",
               identity_status="PENDIENTE", need_hypothesis="", next_best_question="",
               competition_status="INDETERMINADO", run_id, rule_version, payload=None):
    if signal_type not in SIGNAL_TYPES:
        raise ValueError("signal_type no reconocido")
    if competition_status not in COMPETITION:
        raise ValueError("competition_status no reconocido")
    if source_status not in SOURCE_STATUS:
        raise ValueError("source_status no reconocido")
    if not source_id or not source_url or not title or not run_id or not rule_version:
        raise ValueError("source_id, source_url, title, run_id y rule_version son obligatorios")
    sid = str(uuid.uuid4())
    with connect(db_path) as con:
        if company_id and not con.execute("SELECT 1 FROM companies WHERE company_id=?", (company_id,)).fetchone():
            raise ValueError("company_id no existe; crear empresa o dejar identidad sin resolver")
        con.execute("""INSERT INTO signals(
        signal_id,company_id,source_id,source_url,signal_type,title,snippet,published_at,captured_at,
        source_status,identity_status,need_hypothesis,next_best_question,competition_status,
        human_review_status,run_id,rule_version,score_impact,payload_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sid, company_id, source_id, source_url, signal_type, title, snippet, published_at, now_iso(),
         source_status, identity_status, need_hypothesis, next_best_question, competition_status,
         "PENDIENTE", run_id, rule_version, 0.0, json.dumps(payload or {}, ensure_ascii=False)))
    return sid


def review_signal(db_path, signal_id, status, reviewer, reason):
    if status not in REVIEW:
        raise ValueError("estado de revisión no reconocido")
    if not reviewer or not reason:
        raise ValueError("revisor y justificación son obligatorios")
    with connect(db_path) as con:
        cur = con.execute("""UPDATE signals SET human_review_status=?,reviewer=?,reviewed_at=?,review_reason=?
        WHERE signal_id=?""", (status, reviewer, now_iso(), reason, signal_id))
        if cur.rowcount != 1:
            raise ValueError("signal_id no encontrado")


def get_company_dossier(db_path, company_id):
    with connect(db_path) as con:
        company = con.execute("SELECT * FROM companies WHERE company_id=?", (company_id,)).fetchone()
        if not company:
            raise ValueError("company_id no encontrado")
        signals = con.execute("SELECT * FROM signals WHERE company_id=? ORDER BY captured_at DESC", (company_id,)).fetchall()
    return {"company": dict(company), "signals": [dict(s) for s in signals], "signal_count": len(signals),
            "score_impact_total": sum(float(s["score_impact"]) for s in signals)}


def assert_radar_noninterference(before_metrics, after_metrics):
    """Guardrail helper: V3 outputs must remain identical before and after Radar activity."""
    protected = ("score_by_id", "aaa", "aa", "validar", "priority_by_id", "valor_potencial")
    changed = [k for k in protected if before_metrics.get(k) != after_metrics.get(k)]
    if changed:
        raise AssertionError("Regresión: Radar alteró métricas protegidas V3: " + ", ".join(changed))
    return True
