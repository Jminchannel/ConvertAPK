import sys
import unittest
import asyncio
import base64
import zlib
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import admin_client
import main


class _FeedbackUpload:
    def __init__(self, filename, content_type, data):
        self.filename = filename
        self.content_type = content_type
        self.file = BytesIO(data)

    async def read(self):
        return self.file.read()


def _png_chunk(chunk_type, data):
    return (
        len(data).to_bytes(4, "big")
        + chunk_type
        + data
        + (zlib.crc32(chunk_type + data) & 0xFFFFFFFF).to_bytes(4, "big")
    )


class FeedbackProxyTests(unittest.TestCase):
    def test_inbox_proxy_forwards_ticket_credentials(self):
        captured = {}

        def capture_request(path, payload):
            captured["path"] = path
            captured["payload"] = payload
            return {"ok": True, "status_code": 200, "data": []}

        with patch.object(admin_client, "_request_feedback_json", side_effect=capture_request):
            result = admin_client.fetch_feedback_inbox(
                "client_a",
                [{"feedback_id": 7, "access_token": "secret"}],
            )

        self.assertTrue(result["ok"])
        self.assertEqual(captured["path"], "/api/client/feedback/inbox")
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

    def test_feedback_upload_rejects_declared_mime_not_in_allowlist(self):
        image = _FeedbackUpload("reply.bmp", "image/bmp", b"BMnot-an-image")

        with self.assertRaises(main.HTTPException) as raised:
            asyncio.run(main._read_feedback_proxy_uploads([image]))

        self.assertEqual(raised.exception.status_code, 400)

    def test_feedback_upload_rejects_suffix_mismatched_with_mime(self):
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"not-a-complete-png"
        image = _FeedbackUpload("reply.jpg", "image/png", png_bytes)

        with self.assertRaises(main.HTTPException) as raised:
            asyncio.run(main._read_feedback_proxy_uploads([image]))

        self.assertEqual(raised.exception.status_code, 400)

    def test_feedback_upload_rejects_invalid_image_bytes(self):
        image = _FeedbackUpload("reply.png", "image/png", b"not-an-image")

        with self.assertRaises(main.HTTPException) as raised:
            asyncio.run(main._read_feedback_proxy_uploads([image]))

        self.assertEqual(raised.exception.status_code, 400)

    def test_feedback_upload_rejects_png_with_invalid_compressed_pixels(self):
        png_bytes = (
            b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00")
            + _png_chunk(b"IDAT", b"not-zlib")
            + _png_chunk(b"IEND", b"")
        )
        image = _FeedbackUpload("reply.png", "image/png", png_bytes)

        with self.assertRaises(main.HTTPException) as raised:
            asyncio.run(main._read_feedback_proxy_uploads([image]))

        self.assertEqual(raised.exception.status_code, 400)

    def test_feedback_upload_rejects_png_with_invalid_color_type(self):
        png_bytes = (
            b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x05\x00\x00\x00")
            + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00"))
            + _png_chunk(b"IEND", b"")
        )
        image = _FeedbackUpload("reply.png", "image/png", png_bytes)

        with self.assertRaises(main.HTTPException) as raised:
            asyncio.run(main._read_feedback_proxy_uploads([image]))

        self.assertEqual(raised.exception.status_code, 400)

    def test_feedback_upload_rejects_gif_with_invalid_lzw_payload(self):
        gif_bytes = bytearray(base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="))
        gif_bytes[31] = 0xFF
        image = _FeedbackUpload("reply.gif", "image/gif", bytes(gif_bytes))

        with self.assertRaises(main.HTTPException) as raised:
            asyncio.run(main._read_feedback_proxy_uploads([image]))

        self.assertEqual(raised.exception.status_code, 400)

    def test_feedback_upload_rejects_jpeg_sos_without_image_data(self):
        jpeg_bytes = (
            b"\xff\xd8"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
            b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00"
            b"\xff\xd9"
        )
        image = _FeedbackUpload("reply.jpg", "image/jpeg", jpeg_bytes)

        with self.assertRaises(main.HTTPException) as raised:
            asyncio.run(main._read_feedback_proxy_uploads([image]))

        self.assertEqual(raised.exception.status_code, 400)

    def test_feedback_upload_rejects_webp_vp8x_without_image_payload(self):
        webp_bytes = b"RIFF\x16\x00\x00\x00WEBPVP8X\x0a\x00\x00\x00" + (b"\x00" * 10)
        image = _FeedbackUpload("reply.webp", "image/webp", webp_bytes)

        with self.assertRaises(main.HTTPException) as raised:
            asyncio.run(main._read_feedback_proxy_uploads([image]))

        self.assertEqual(raised.exception.status_code, 400)

    def test_feedback_upload_accepts_valid_gif(self):
        gif_bytes = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")
        image = _FeedbackUpload("reply.gif", "image/gif", gif_bytes)

        result = asyncio.run(main._read_feedback_proxy_uploads([image]))

        self.assertEqual(result[0]["content_type"], "image/gif")
        self.assertEqual(result[0]["data"], gif_bytes)

    def test_inbox_proxy_maps_upstream_access_failure_to_forbidden(self):
        payload = main.FeedbackInboxProxyRequest(client_id="client_a", tickets=[])
        with patch.object(main, "fetch_feedback_inbox", return_value={"ok": False, "status_code": 401}):
            with self.assertRaises(main.HTTPException) as raised:
                asyncio.run(main.adminhub_feedback_inbox(payload))

        self.assertEqual(raised.exception.status_code, 403)

    def test_initial_feedback_proxy_maps_upstream_access_failure_to_forbidden(self):
        with patch.object(main, "submit_feedback", return_value={"ok": False, "status_code": 401}):
            with self.assertRaises(main.HTTPException) as raised:
                asyncio.run(main.adminhub_feedback("client_a", "hello", "{}", []))

        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
