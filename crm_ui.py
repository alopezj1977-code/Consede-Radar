"""Streamlit UI for workspace-scoped CRM and human-validated commercial evidence."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from core import identify_columns
from crm_store import STAGES, ensure_schema, list_accounts, list_events, upsert_account


def _workspace_id():
    try:
        cfg = st.secrets.get("mailing", {})
        return str(cfg.get("workspace_id") or "4msfts").strip()
    except Exception:
        return "4msfts"


def render_crm_ui(result_df):
    st.markdown("### CRM · Seguimiento y evidencia comercial")
    st.caption(
        "El CRM registra actividad, responsable y evidencia humana por ID DENUE. "
        "No modifica Score V3 ni convierte señales del Radar en necesidades confirmadas."
    )
    workspace_id = _workspace_id()
    try:
        try:
            database_url = st.secrets.get("DATABASE_URL", "")
        except Exception:
            database_url = ""
        if database_url and not os.getenv("DATABASE_URL"):
            os.environ["DATABASE_URL"] = str(database_url)
        ensure_schema()
        storage = "Neon" if os.getenv("DATABASE_URL") else "SQLite local"
        st.caption(f"Persistencia: {storage} · Workspace: {workspace_id}")
    except Exception as exc:
        st.error(f"No se pudo inicializar el CRM; no se guardó información: {exc}")
        return

    mapping = identify_columns(result_df) if isinstance(result_df, pd.DataFrame) else {}
    id_col = mapping.get("id")
    name_col = mapping.get("name") or mapping.get("razon")
    if result_df is None or result_df.empty or not id_col or not name_col:
        st.warning("Ejecuta una corrida V3 con ID DENUE y nombre de empresa reconocibles para iniciar el seguimiento.")
        return

    candidates = result_df[[id_col, name_col]].copy()
    candidates[id_col] = candidates[id_col].astype(str).str.strip()
    candidates[name_col] = candidates[name_col].fillna("").astype(str).str.strip()
    candidates = candidates[(candidates[id_col] != "") & (~candidates[id_col].str.casefold().isin(["nan", "none"]))]
    candidates = candidates.drop_duplicates(subset=[id_col])
    candidates = candidates[candidates[name_col] != ""]
    if candidates.empty:
        st.warning("La corrida no contiene empresas con ID y nombre utilizables.")
        return

    labels = {f"{row[name_col]} · DENUE {row[id_col]}": (row[id_col], row[name_col])
              for _, row in candidates.iterrows()}
    selected_label = st.selectbox("Empresa de la corrida", list(labels), key="crm_company_select")
    denue_id, company_name = labels[selected_label]

    existing = {row["denue_id"]: row for row in list_accounts(workspace_id)}
    current = existing.get(denue_id, {})
    with st.form("crm_account_form"):
        left, right = st.columns(2)
        with left:
            stage = st.selectbox("Etapa comercial", STAGES,
                index=STAGES.index(current["stage"]) if current.get("stage") in STAGES else 0)
            owner = st.text_input("Responsable comercial", value=current.get("owner", ""))
            contact_name = st.text_input("Nombre del contacto", value=current.get("contact_name", ""))
            contact_email = st.text_input("Correo del contacto", value=current.get("contact_email", ""))
        with right:
            interest = st.checkbox("Interés comercial confirmado", value=bool(current.get("interest_confirmed", False)))
            need_evidence = st.text_area("Evidencia objetiva de necesidad", value=current.get("need_evidence", ""),
                help="Describe lo que el prospecto confirmó; no uses una inferencia del Radar.")
            evidence_source = st.text_input("Fuente / referencia de evidencia", value=current.get("evidence_source", ""),
                help="Referencia verificable: minuta, correo, llamada documentada o documento.")
            next_action = st.text_input("Siguiente acción", value=current.get("next_action", ""))
            next_action_date = st.text_input("Fecha de siguiente acción (AAAA-MM-DD)", value=current.get("next_action_date", ""))
        actor = st.text_input("Quién registra / valida", value=current.get("owner", ""))
        submitted = st.form_submit_button("Guardar seguimiento comercial", type="primary")

    if submitted:
        try:
            account_id = upsert_account(
                workspace_id, denue_id=denue_id, company_name=company_name, stage=stage,
                owner=owner, contact_name=contact_name, contact_email=contact_email,
                interest_confirmed=interest, need_evidence=need_evidence,
                evidence_source=evidence_source, next_action=next_action,
                next_action_date=next_action_date, actor=actor,
            )
            st.success(f"Seguimiento guardado · expediente {account_id[:8]}. Score V3 intacto.")
            st.rerun()
        except Exception as exc:
            st.error(f"No se guardó el seguimiento: {exc}")

    accounts = list_accounts(workspace_id)
    st.markdown("#### Cartera CRM del workspace")
    if accounts:
        frame = pd.DataFrame(accounts)
        frame["interest_confirmed"] = frame["interest_confirmed"].map({1: "Sí", 0: "No", True: "Sí", False: "No"})
        st.dataframe(frame, use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay expedientes CRM en este workspace.")

    with st.expander("Historial de la empresa seleccionada"):
        events = list_events(workspace_id, denue_id)
        if events:
            st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
        else:
            st.caption("Aún no hay eventos registrados.")
