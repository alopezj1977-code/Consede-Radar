"""Microsoft Graph delivery for CONCEDE Motor V3."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode
import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
import msal
import requests

APPROVED_SENDER_MAILBOX = "C@4msfts.com"
GRAPH_SCOPES = ["Mail.Send", "User.Read"]
MAX_CAMPAIGN_RECIPIENTS = 500


class MailDeliveryError(RuntimeError):
    """Safe-to-display Microsoft 365 authentication or delivery failure."""


def read_mail_config(secrets: Any) -> tuple[dict[str, str], list[str]]:
    try:
        raw = secrets.get("mailing", {})
    except Exception:
        raw = {}
    keys = ("tenant_id", "client_id", "client_secret", "sender_mailbox")
    config = {key: str(raw.get(key, "")).strip() for key in keys}
    config["redirect_uri"] = str(raw.get("redirect_uri", "")).strip()
    config["workspace_id"] = str(raw.get("workspace_id", "4msfts")).strip() or "4msfts"
    missing = [key for key, value in config.items() if key != "redirect_uri" and not value]
    if config.get("sender_mailbox", "").casefold() != APPROVED_SENDER_MAILBOX.casefold():
        if "sender_mailbox" not in missing:
            missing.append("sender_mailbox")
    return config, missing


def new_token_cache(serialized: str | None = None) -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if serialized:
        try:
            cache.deserialize(serialized)
        except (ValueError, TypeError):
            pass
    return cache


def _client(config, cache):
    if any(not config.get(k) for k in ("tenant_id", "client_id", "client_secret")):
        raise MailDeliveryError("Falta configurar Microsoft Entra en los secretos de Streamlit.")
    return msal.ConfidentialClientApplication(
        client_id=config["client_id"],
        client_credential=config["client_secret"],
        authority=f"https://login.microsoftonline.com/{quote(config['tenant_id'], safe='')}",
        token_cache=cache,
    )


def start_mail_sign_in(config, redirect_uri, cache):
    try:
        return _client(config, cache).initiate_auth_code_flow(
            scopes=GRAPH_SCOPES,
            redirect_uri=redirect_uri,
            login_hint=APPROVED_SENDER_MAILBOX,
        )
    except Exception as exc:
        raise MailDeliveryError("No se pudo iniciar la autenticación de Microsoft 365.") from exc


def _flow_cipher(config):
    secret = config.get("client_secret", "")
    if not secret:
        raise MailDeliveryError("Falta el secreto de aplicación para proteger el flujo OAuth.")
    key = base64.urlsafe_b64encode(
        hashlib.sha256(("CONCEDEMotorOAuth:" + secret).encode()).digest()
    )
    return Fernet(key)


def protect_mail_auth_flow(config, flow):
    payload = {k: v for k, v in flow.items() if k not in ("auth_uri", "state")}
    token = _flow_cipher(config).encrypt(json.dumps(payload).encode()).decode("ascii")
    parts = urlsplit(flow["auth_uri"])
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "state"]
    query.append(("state", token))
    auth_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return auth_url, token


def restore_mail_auth_flow(config, state):
    try:
        payload = _flow_cipher(config).decrypt(state.encode("ascii"), ttl=600)
        flow = json.loads(payload.decode())
    except (InvalidToken, ValueError, TypeError, UnicodeError) as exc:
        raise MailDeliveryError(
            "El estado OAuth no es válido o expiró. Inicia sesión nuevamente."
        ) from exc
    # The encrypted state token is the value Microsoft returns to the callback.
    flow["state"] = state
    return flow


def complete_mail_sign_in(config, flow, auth_response, cache):
    try:
        result = _client(config, cache).acquire_token_by_auth_code_flow(flow, auth_response)
    except Exception as exc:
        raise MailDeliveryError("Microsoft no pudo completar la autenticación.") from exc
    if not result.get("access_token"):
        detail = result.get("error_description") or result.get("error") or "Error de autenticación"
        raise MailDeliveryError(f"Microsoft Graph no autorizó la sesión: {detail[:400]}")
    return result


def get_cached_mail_token(config, cache):
    try:
        app = _client(config, cache)
        accounts = app.get_accounts(username=APPROVED_SENDER_MAILBOX) or app.get_accounts()
        if not accounts:
            return None
        result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])
        return result.get("access_token") if result else None
    except Exception:
        return None


def get_signed_in_mailbox(access_token, *, http=requests):
    try:
        response = http.get(
            "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise MailDeliveryError("No fue posible validar la cuenta en Microsoft Graph.") from exc
    if response.status_code != 200:
        raise MailDeliveryError(
            f"Microsoft Graph no pudo validar la cuenta (HTTP {response.status_code})."
        )
    try:
        payload = response.json()
    except (ValueError, TypeError) as exc:
        raise MailDeliveryError("Microsoft Graph devolvió una respuesta de cuenta inválida.") from exc
    mailbox = (payload.get("mail") or payload.get("userPrincipalName") or "").strip()
    if not mailbox:
        raise MailDeliveryError("Microsoft Graph no devolvió la cuenta autenticada.")
    return mailbox


def send_graph_mail(config, recipients, subject, body, *, access_token, http=requests):
    clean = list(dict.fromkeys(a.strip() for a in recipients if a and a.strip()))
    if not clean:
        raise MailDeliveryError("El borrador no contiene destinatarios.")
    if len(clean) > MAX_CAMPAIGN_RECIPIENTS:
        raise MailDeliveryError(
            f"Una campaña no puede superar {MAX_CAMPAIGN_RECIPIENTS} destinatarios por envío."
        )
    if not subject.strip() or not body.strip():
        raise MailDeliveryError("El asunto y el mensaje son obligatorios.")
    if config.get("sender_mailbox", "").casefold() != APPROVED_SENDER_MAILBOX.casefold():
        raise MailDeliveryError(f"El remitente debe ser {APPROVED_SENDER_MAILBOX}.")
    if not access_token:
        raise MailDeliveryError("Primero conecta Microsoft 365 con C@4msfts.com.")

    # Enforce the approved mailbox at the delivery boundary, not only in the UI.
    mailbox = get_signed_in_mailbox(access_token, http=http)
    if mailbox.casefold() != APPROVED_SENDER_MAILBOX.casefold():
        raise MailDeliveryError(
            f"La sesión pertenece a {mailbox}; el envío solo está autorizado desde "
            f"{APPROVED_SENDER_MAILBOX}."
        )

    try:
        response = http.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "message": {
                    "subject": subject.strip(),
                    "body": {"contentType": "Text", "content": body.strip()},
                    "bccRecipients": [{"emailAddress": {"address": a}} for a in clean],
                },
                "saveToSentItems": True,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise MailDeliveryError("No fue posible conectar con Microsoft Graph.") from exc
    if response.status_code != 202:
        raise MailDeliveryError(
            f"Microsoft Graph rechazó el envío (HTTP {response.status_code}). "
            "El correo no se marcó como enviado."
        )
    return {"accepted": True, "recipient_count": len(clean), "http_status": 202}
