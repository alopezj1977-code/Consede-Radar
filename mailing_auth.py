"""Delegated Microsoft 365 sign-in for CONCEDE Motor V3."""
from __future__ import annotations

from html import escape
from urllib.parse import urlsplit, urlunsplit

import streamlit as st

from mailing_service import (
    APPROVED_SENDER_MAILBOX,
    MailDeliveryError,
    complete_mail_sign_in,
    get_cached_mail_token,
    get_signed_in_mailbox,
    new_token_cache,
    protect_mail_auth_flow,
    read_mail_config,
    restore_mail_auth_flow,
    start_mail_sign_in,
)


def _redirect_uri(config: dict[str, str]) -> str:
    """Use an explicitly configured callback or derive the active Streamlit URL."""
    configured = (config.get("redirect_uri") or "").strip()
    candidate = configured
    if not candidate:
        try:
            candidate = st.context.url
        except Exception:
            candidate = ""
    if not candidate:
        raise MailDeliveryError(
            "No se pudo determinar la URL pública de CONCEDE. Configura "
            "mailing.redirect_uri en los secretos de Streamlit y registra esa misma "
            "URL como Redirect URI tipo Web en Microsoft Entra."
        )
    parts = urlsplit(candidate)
    if parts.scheme not in {"https", "http"} or not parts.netloc:
        raise MailDeliveryError("La Redirect URI de Microsoft 365 no es una URL válida.")
    if parts.scheme != "https" and parts.hostname not in {"localhost", "127.0.0.1"}:
        raise MailDeliveryError("La Redirect URI debe usar HTTPS.")
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", ""))


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
            st.error(str(exc))
            return None

    token = get_cached_mail_token(config, cache)
    if token:
        st.session_state["concede_mail_token_cache"] = cache.serialize()
        try:
            mailbox = get_signed_in_mailbox(token)
        except MailDeliveryError as exc:
            st.error(str(exc))
            return None
        if mailbox.casefold() != APPROVED_SENDER_MAILBOX.casefold():
            st.session_state.pop("concede_mail_access_token", None)
            st.error(
                f"Sesión iniciada con {mailbox}. El módulo solo acepta "
                f"{APPROVED_SENDER_MAILBOX}."
            )
            return None
        st.session_state["concede_mail_access_token"] = token
        st.success(f"Microsoft 365 conectado · {APPROVED_SENDER_MAILBOX}")
        return token

    st.session_state.pop("concede_mail_access_token", None)
    try:
        redirect_uri = _redirect_uri(config)
        flow = start_mail_sign_in(config, redirect_uri, cache)
        auth_url, _ = protect_mail_auth_flow(config, flow)
    except MailDeliveryError as exc:
        st.error(str(exc))
        return None

    if not auth_url:
        st.error("Microsoft no generó la dirección de inicio de sesión.")
        return None

    st.warning("Conecta el buzón autorizado para habilitar el envío.")
    st.markdown(
        f'<a href="{escape(auth_url, quote=True)}" target="_top" '
        'style="display:inline-block;padding:.7rem 1rem;background:#185abd;'
        'color:white;border-radius:8px;text-decoration:none;font-weight:650">'
        'Conectar Microsoft 365 · C@4msfts.com</a>',
        unsafe_allow_html=True,
    )
    st.caption("Autenticación delegada. No se usan permisos de aplicación.")
    return None
