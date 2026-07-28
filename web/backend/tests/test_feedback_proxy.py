import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import admin_client
import main


class FeedbackProxyTests(unittest.TestCase):
    def test_inbox_proxy_forwards_ticket_credentials(self):
        captured = {}

        def capture_request(*args, **kwargs):
            captured.update(kwargs)
            return []

        with patch.object(admin_client, "_request_json", side_effect=capture_request):
            admin_client.fetch_feedback_inbox(
                "client_a",
                [{"feedback_id": 7, "access_token": "secret"}],
            )

        self.assertEqual(captured["payload"]["tickets"][0]["access_token"], "secret")

    def test_submit_feedback_returns_only_new_ticket_credentials(self):
        with patch.object(
            admin_client,
            "_request_feedback_multipart",
            return_value={
                "ok": True,
                "status_code": 200,
                "data": {"ok": True, "id": 7, "access_token": "new-secret"},
            },
        ):
            result = admin_client.submit_feedback("client_a", "hello", {"os": "Windows"}, [])

        self.assertEqual(
            result,
            {"ok": True, "feedback_id": 7, "access_token": "new-secret"},
        )

    def test_read_ack_sends_ticket_secret_in_request_body(self):
        with patch.object(
            admin_client,
            "_request_feedback_json",
            return_value={"ok": True, "status_code": 200, "data": {"ok": True}},
        ) as request_json:
            result = admin_client.acknowledge_feedback_message(7, 11, "client_a", "secret")

        self.assertTrue(result["ok"])
        self.assertEqual(
            request_json.call_args.args,
            (
                "/api/client/feedback/7/messages/11/read",
                {"client_id": "client_a", "access_token": "secret"},
            ),
        )
        self.assertNotIn("secret", request_json.call_args.args[0])
        self.assertEqual(
            request_json.call_args.args[1],
            {"client_id": "client_a", "access_token": "secret"},
        )

    def test_attachment_proxy_rejects_unexpected_content_type(self):
        payload = type("TicketPayload", (), {"client_id": "client_a", "access_token": "secret"})()
        with patch.object(
            main,
            "download_feedback_attachment",
            return_value={
                "ok": True,
                "status_code": 200,
                "content": b"not-an-image",
                "content_type": "text/plain",
            },
        ):
            with self.assertRaises(main.HTTPException) as raised:
                asyncio.run(main.adminhub_feedback_attachment(7, 11, 0, payload))

        self.assertEqual(raised.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
