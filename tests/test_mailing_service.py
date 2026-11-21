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
