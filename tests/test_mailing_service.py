import unittest

from mailing_service import (
    APPROVED_SENDER_MAILBOX,
    MailDeliveryError,
    read_mail_config,
    send_graph_mail,
)


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeGraph:
    def __init__(self, mailbox=APPROVED_SENDER_MAILBOX, send_status=202):
        self.mailbox = mailbox
        self.send_status = send_status
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse(200, {"mail": self.mailbox})

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse(self.send_status)


class MailingServiceTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "not-a-real-secret",
            "sender_mailbox": APPROVED_SENDER_MAILBOX,
        }

    def test_config_requires_exact_approved_sender(self):
        config, missing = read_mail_config({
            "mailing": {**self.config, "sender_mailbox": "other@example.com"}
        })
        self.assertIn("sender_mailbox", missing)

    def test_send_checks_graph_identity_before_delivery(self):
        graph = FakeGraph(mailbox="other@example.com")
        with self.assertRaises(MailDeliveryError):
            send_graph_mail(
                self.config, ["buyer@example.com"], "Subject", "Body",
                access_token="token", http=graph,
            )
        self.assertEqual(len(graph.get_calls), 1)
        self.assertEqual(len(graph.post_calls), 0)

    def test_send_uses_bcc_and_accepts_http_202(self):
        graph = FakeGraph()
        result = send_graph_mail(
            self.config,
            ["buyer@example.com", "buyer@example.com", "second@example.com"],
            "  Subject  ",
            "  Body  ",
            access_token="token",
            http=graph,
        )
        self.assertEqual(result, {
            "accepted": True, "recipient_count": 2, "http_status": 202
        })
        payload = graph.post_calls[0][1]["json"]
        self.assertEqual(
            [x["emailAddress"]["address"] for x in payload["message"]["bccRecipients"]],
            ["buyer@example.com", "second@example.com"],
        )
        self.assertTrue(payload["saveToSentItems"])

    def test_send_rejects_graph_failure(self):
        graph = FakeGraph(send_status=403)
        with self.assertRaisesRegex(MailDeliveryError, "HTTP 403"):
            send_graph_mail(
                self.config, ["buyer@example.com"], "Subject", "Body",
                access_token="token", http=graph,
            )

    def test_send_enforces_campaign_recipient_limit(self):
        graph = FakeGraph()
        recipients = [f"user{i}@example.com" for i in range(501)]
        with self.assertRaisesRegex(MailDeliveryError, "500 destinatarios"):
            send_graph_mail(
                self.config, recipients, "Subject", "Body",
                access_token="token", http=graph,
            )
        self.assertEqual(graph.get_calls, [])
        self.assertEqual(graph.post_calls, [])


if __name__ == "__main__":
    unittest.main()

from urllib.parse import parse_qs, urlsplit

from mailing_service import protect_mail_auth_flow, restore_mail_auth_flow
from mailing_store import ensure_schema, get_latest_draft, list_contacts, mark_accepted, save_draft, upsert_contacts, validate_campaign_recipients


def test_oauth_state_round_trip_is_encrypted_and_restorable():
    config = {"client_secret": "test-secret"}
    flow = {
        "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=x&state=original",
        "state": "original",
        "redirect_uri": "https://example.streamlit.app/",
        "token_endpoint": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "code_verifier": "verifier",
    }
    auth_url, protected_state = protect_mail_auth_flow(config, flow)
    assert "original" not in protected_state
    restored = restore_mail_auth_flow(config, protected_state)
    assert restored["state"] == protected_state
    assert restored["code_verifier"] == "verifier"
    assert parse_qs(urlsplit(auth_url).query)["state"][0] == protected_state


def test_mailing_store_is_workspace_scoped_and_draft_lifecycle(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db = tmp_path / "mailing.sqlite3"
    ensure_schema(db_path=db)
    contacts = [{
        "empresa": "Empresa A",
        "correo": "persona@example.com",
        "contacto": "Persona",
        "fuente": "https://example.com",
        "autorizado": True,
        "correo_valido": True,
        "apto": True,
    }]
    assert upsert_contacts("workspace-a", contacts, db_path=db) == 1
    assert len(list_contacts("workspace-a", db_path=db)) == 1
    assert list_contacts("workspace-b", db_path=db) == []

    draft = {
        "id": "campaign-1",
        "name": "Prueba",
        "subject": "Asunto",
        "body": "Mensaje",
        "recipients": ["persona@example.com"],
    }
    save_draft("workspace-a", draft, db_path=db)
    assert get_latest_draft("workspace-a", db_path=db)["id"] == "campaign-1"
    mark_accepted("workspace-a", "campaign-1", db_path=db)
    assert get_latest_draft("workspace-a", db_path=db) is None


def test_campaign_rechecks_current_consent_before_send(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db = tmp_path / "consent.sqlite3"
    ensure_schema(db_path=db)
    contact = {
        "empresa": "Empresa",
        "correo": "persona@example.com",
        "contacto": "Persona",
        "fuente": "Referencia",
        "autorizado": True,
        "correo_valido": True,
        "apto": True,
    }
    upsert_contacts("workspace-a", [contact], db_path=db)
    allowed, blocked = validate_campaign_recipients(
        "workspace-a", ["persona@example.com"], db_path=db
    )
    assert allowed == ["persona@example.com"]
    assert blocked == []

    contact["autorizado"] = False
    contact["apto"] = False
    upsert_contacts("workspace-a", [contact], db_path=db)
    allowed, blocked = validate_campaign_recipients(
        "workspace-a", ["persona@example.com"], db_path=db
    )
    assert allowed == []
    assert blocked == ["persona@example.com"]
