"""Delegated Microsoft 365 sign-in for CONCEDE Motor V3."""
from __future__ import annotations
from html import escape
import streamlit as st
from mailing_service import (APPROVED_SENDER_MAILBOX, MailDeliveryError, complete_mail_sign_in,
    get_cached_mail_token, get_signed_in_mailbox, new_token_cache, protect_mail_auth_flow,
    restore_mail_auth_flow, start_mail_sign_in)

REDIRECT_URI = "https://concede-motor-v3.streamlit.app/"

def render_mail_auth(config: dict[str, str]) -> str | None:
    cache = new_token_cache(st.session_state.get("concede_mail_token_cache"))
    params = st.query_params.to_dict()
    if params.get("code"):
        try:
            flow = restore_mail_auth_flow(config, params.get("state", ""))
            complete_mail_sign_in(config, flow, params, cache)
            st.session_state["concede_mail_token_cache"] = cache.serialize()
            st.query_params.clear()
            st.rerun()
        except MailDeliveryError as exc:
            st.error(str(exc)); return None
    token = get_cached_mail_token(config, cache)
    if token:
        st.session_state["concede_mail_token_cache"] = cache.serialize()
        try: mailbox = get_signed_in_mailbox(token)
        except MailDeliveryError as exc: st.error(str(exc)); return None
        if mailbox.casefold() != APPROVED_SENDER_MAILBOX.casefold():
            st.error(f"Sesión iniciada con {mailbox}. El módulo solo acepta {APPROVED_SENDER_MAILBOX}.")
            return None
        st.session_state["concede_mail_access_token"] = token
        st.success(f"Microsoft 365 conectado · {APPROVED_SENDER_MAILBOX}")
        return token
    try:
        flow = start_mail_sign_in(config, REDIRECT_URI, cache)
        auth_url, _ = protect_mail_auth_flow(config, flow)
    except MailDeliveryError as exc:
        st.error(str(exc)); return None
    if not auth_url: st.error("Microsoft no generó la dirección de inicio de sesión."); return None
    st.warning("Conecta el buzón autorizado para habilitar el envío.")
    st.markdown(f'<a href="{escape(auth_url, quote=True)}" target="_top" style="display:inline-block;padding:.7rem 1rem;background:#185abd;color:white;border-radius:8px;text-decoration:none;font-weight:650">Conectar Microsoft 365 · C@4msfts.com</a>', unsafe_allow_html=True)
    st.caption("Autenticación delegada. No se usan permisos de aplicación.")
    return None
