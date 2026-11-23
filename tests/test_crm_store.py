import pytest

from crm_store import STAGES, ensure_schema, list_accounts, list_events, upsert_account


def test_crm_account_is_workspace_scoped_and_persists_history(tmp_path):
    db = tmp_path / "crm.sqlite3"
    ensure_schema(db)
    account_id = upsert_account(
        "workspace-a", denue_id="DENUE-001", company_name="Empresa Uno",
        stage="PROSPECTO", owner="Santy", actor="Santy", db_path=db,
    )
    upsert_account(
        "workspace-a", denue_id="DENUE-001", company_name="Empresa Uno",
        stage="CONTACTO", owner="Santy", actor="Santy",
        contact_name="Contacto", contact_email="contacto@example.com",
        next_action="Agendar llamada", next_action_date="2026-11-25", db_path=db,
    )
    assert len(list_accounts("workspace-a", db)) == 1
    assert list_accounts("workspace-b", db) == []
    events = list_events("workspace-a", "DENUE-001", db)
    assert any(event["event_type"] == "STAGE_CHANGE" and event["new_stage"] == "CONTACTO" for event in events)
    assert account_id


def test_crm_rejects_interest_without_documented_need_evidence(tmp_path):
    db = tmp_path / "crm.sqlite3"
    ensure_schema(db)
    with pytest.raises(ValueError, match="requiere evidencia"):
        upsert_account(
            "workspace-a", denue_id="DENUE-002", company_name="Empresa Dos",
            stage="INTERÉS", owner="Santiago", actor="Santiago",
            interest_confirmed=True, need_evidence="",
            evidence_source="", db_path=db,
        )


def test_crm_rejects_unknown_stage_and_missing_denue_id(tmp_path):
    db = tmp_path / "crm.sqlite3"
    ensure_schema(db)
    with pytest.raises(ValueError, match="Etapa CRM"):
        upsert_account(
            "workspace-a", denue_id="DENUE-003", company_name="Empresa Tres",
            stage="AAA", owner="Santy", actor="Santy", db_path=db,
        )
    with pytest.raises(ValueError, match="ID DENUE"):
        upsert_account(
            "workspace-a", denue_id="", company_name="Empresa Tres",
            stage=STAGES[0], owner="Santy", actor="Santy", db_path=db,
        )
