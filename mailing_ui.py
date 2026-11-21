"""Mailing workspace for CONCEDE V3. Contacts and drafts are session-scoped in this pilot."""
from __future__ import annotations
import re
import uuid
import pandas as pd
import streamlit as st
from mailing_auth import render_mail_auth
from mailing_service import APPROVED_SENDER_MAILBOX, MailDeliveryError, read_mail_config, send_graph_mail

_TRUE = {"SI", "SÍ", "TRUE", "1", "AUTORIZADO", "YES", "Y"}

def _read_contacts(uploaded):
    try:
        try: frame = pd.read_csv(uploaded, encoding="utf-8-sig", dtype=str).fillna("")
        except UnicodeDecodeError:
            uploaded.seek(0); frame = pd.read_csv(uploaded, encoding="latin1", dtype=str).fillna("")
    except Exception as exc: raise ValueError(f"No se pudo leer el CSV: {exc}") from exc
    aliases = {
        "empresa": ["empresa", "razon social", "razón social", "company", "nombre empresa"],
        "correo": ["correo", "email", "e-mail", "correo electronico", "correo electrónico"],
        "contacto": ["contacto", "nombre", "contact name", "persona"],
        "fuente": ["fuente", "source", "origen del correo"],
        "autorizado": ["autorizado", "consentimiento", "permiso", "authorization"]}
    normalized = {str(c).strip().casefold(): c for c in frame.columns}
    mapping = {key: next((normalized[n] for n in names if n in normalized), None) for key, names in aliases.items()}
    missing = [key for key, col in mapping.items() if col is None]
    if missing: raise ValueError("Faltan columnas obligatorias: " + ", ".join(missing))
    result = pd.DataFrame({key: frame[col].astype(str).str.strip() for key, col in mapping.items()})
    result["correo"] = result["correo"].str.lower()
    result["correo_valido"] = result["correo"].map(lambda v: bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", v)))
    result["autorizado"] = result["autorizado"].str.upper().isin(_TRUE)
    result["apto"] = result["correo_valido"] & result["autorizado"] & result["fuente"].ne("")
    return result.drop_duplicates(subset=["correo"]).reset_index(drop=True)

def render_mailing_ui(result_df=None, metrics=None, config=None):
    st.markdown("### Mailing · Activación comercial")
    st.caption("Contactos documentados, campañas, borradores y envío aprobado desde Microsoft 365.")
    if isinstance(result_df, pd.DataFrame) and not result_df.empty:
        candidates = result_df
        if "Candidato_Comercial" in candidates.columns:
            candidates = candidates[candidates["Candidato_Comercial"].fillna(False)]
        st.metric("Candidatos comerciales en la corrida activa", f"{len(candidates):,}")
        if not candidates.empty:
            st.download_button("Exportar candidatos de CONCEDE (CSV)",
                candidates.to_csv(index=False).encode("utf-8-sig"),
                "concede_candidatos_para_activacion.csv", "text/csv")
        st.caption("La exportación no contiene contactos verificados por sí misma. Los correos requieren fuente y autorización documentadas.")
    if "concede_mail_contacts" not in st.session_state: st.session_state["concede_mail_contacts"] = pd.DataFrame()
    if "concede_mail_draft" not in st.session_state: st.session_state["concede_mail_draft"] = None
    mail_config, missing = read_mail_config(st.secrets)
    contacts_tab, campaign_tab, m365_tab, send_tab = st.tabs(["Contactos", "Campañas", "Microsoft 365", "Aprobación y envío"])

    with contacts_tab:
        st.markdown("**Base de contactos autorizados**")
        st.write("CSV requerido: empresa, correo, contacto, fuente y autorizado. Solo correos válidos con fuente y autorización afirmativa pueden entrar a una campaña.")
        sample = pd.DataFrame([{"empresa":"Empresa ejemplo","correo":"contacto@empresa.com","contacto":"Nombre del contacto","fuente":"URL o referencia de origen","autorizado":"SI"}])
        st.download_button("Descargar plantilla CSV", sample.to_csv(index=False).encode("utf-8-sig"), "plantilla_contactos_concede.csv", "text/csv")
        upload = st.file_uploader("Importar contactos (CSV)", type=["csv"], key="concede_mail_contacts_upload")
        if upload is not None and st.button("Validar e importar contactos", type="primary"):
            try:
                parsed = _read_contacts(upload)
                st.session_state["concede_mail_contacts"] = parsed
                st.success(f"Contactos importados: {len(parsed):,} · aptos para campaña: {int(parsed['apto'].sum()):,}")
            except ValueError as exc: st.error(str(exc))
        contacts = st.session_state["concede_mail_contacts"]
        if not contacts.empty:
            st.dataframe(contacts[["empresa","contacto","correo","fuente","autorizado","apto"]], use_container_width=True, hide_index=True)
            st.caption("Los contactos no aptos se conservan visibles para corrección, pero no pueden enviarse.")

    with campaign_tab:
        contacts = st.session_state["concede_mail_contacts"]
        if contacts.empty or not contacts["apto"].any():
            st.info("Primero importa contactos con correo válido, fuente y autorización documentada.")
        else:
            eligible = contacts[contacts["apto"]]
            options = {f"{row.empresa} · {row.correo}": row.correo for row in eligible.itertuples(index=False)}
            selected = st.multiselect("Destinatarios", list(options), key="concede_mail_selected")
            campaign_name = st.text_input("Nombre de campaña", "CONCEDE · Activación comercial", key="concede_mail_campaign_name")
            subject = st.text_input("Asunto", key="concede_mail_subject")
            body = st.text_area("Mensaje", height=230, key="concede_mail_body")
            if selected:
                selected_rows = eligible[eligible["correo"].isin([options[item] for item in selected])]
                st.markdown("**Destinatarios seleccionados**")
                st.dataframe(selected_rows[["empresa","contacto","correo","fuente"]], use_container_width=True, hide_index=True)
            if st.button("Guardar borrador", type="primary"):
                if not selected: st.error("Selecciona al menos un destinatario.")
                elif not subject.strip() or not body.strip(): st.error("El asunto y el mensaje son obligatorios.")
                else:
                    st.session_state["concede_mail_draft"] = {"id":str(uuid.uuid4()),"name":campaign_name.strip(),"subject":subject.strip(),"body":body.strip(),"recipients":[options[item] for item in selected]}
                    st.success("Borrador guardado en esta sesión. No se ha enviado ningún correo.")
        draft = st.session_state.get("concede_mail_draft")
        if draft: st.info(f"Borrador actual: {draft['name']} · {len(draft['recipients'])} destinatario(s)")

    with m365_tab:
        st.markdown("**Buzón institucional autorizado**")
        st.write(f"Remitente permitido: **{APPROVED_SENDER_MAILBOX}**")
        if missing:
            st.warning("Falta configurar en Streamlit Secrets: " + ", ".join(missing))
            st.code('[mailing]\ntenant_id = "..."\nclient_id = "..."\nclient_secret = "..."\nsender_mailbox = "C@4msfts.com"', language="toml")
        else: render_mail_auth(mail_config)

    with send_tab:
        draft = st.session_state.get("concede_mail_draft")
        if not draft: st.info("No hay un borrador listo para aprobación.")
        else:
            st.markdown(f"**{draft['name']}**")
            st.write(f"Remitente: {APPROVED_SENDER_MAILBOX} · Destinatarios: {len(draft['recipients'])}")
            st.dataframe(st.session_state["concede_mail_contacts"].loc[
                st.session_state["concede_mail_contacts"]["correo"].isin(draft["recipients"]),
                ["empresa","contacto","correo","fuente"]], use_container_width=True, hide_index=True)
            st.text(f"Asunto: {draft['subject']}\n\n{draft['body']}")
            st.warning("El envío ocurre solo al pulsar el botón final. Los destinatarios se envían en copia oculta (BCC).")
            approved = st.checkbox("Apruebo expresamente el contenido y la lista completa de destinatarios para enviar desde C@4msfts.com.", key=f"concede_mail_explicit_approval_{draft['id']}")
            token = st.session_state.get("concede_mail_access_token")
            if not token: st.info("Conecta Microsoft 365 en la pestaña correspondiente antes de enviar.")
            if st.button("Enviar campaña aprobada", type="primary", disabled=(not approved or not token)):
                try:
                    outcome = send_graph_mail(mail_config, draft["recipients"], draft["subject"], draft["body"], access_token=token)
                    st.success(f"Microsoft Graph aceptó el envío a {outcome['recipient_count']} destinatario(s). HTTP 202 confirma aceptación, no entrega final.")
                    st.session_state["concede_mail_last_send"] = {"campaign":draft["name"],"recipient_count":outcome["recipient_count"],"status":"ACEPTADO_POR_GRAPH"}
                    st.session_state["concede_mail_draft"] = None
                except MailDeliveryError as exc: st.error(str(exc))
