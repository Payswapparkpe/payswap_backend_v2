import base64

from django.test import TestCase

from django.core.files.storage import default_storage

from portal.services.connect_attachment_storage import MAX_CONNECT_MEDIA_BYTES, persist_connect_binary_from_data_url

# 1x1 PNG
_TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


class ConnectAttachmentStorageTests(TestCase):
    def test_persist_strips_data_url_and_stores_file(self):
        meta = {"data_url": f"data:image/png;base64,{_TINY_PNG_B64}", "file_name": "x.png"}
        out = persist_connect_binary_from_data_url(thread_id=42, metadata=meta)
        self.assertNotIn("data_url", out)
        self.assertIn("storage_path", out)
        self.assertEqual(out.get("mime_type"), "image/png")
        self.assertTrue(default_storage.exists(out["storage_path"]))

    def test_rejects_oversized_payload(self):
        raw = b"x" * (MAX_CONNECT_MEDIA_BYTES + 1)
        b64 = base64.b64encode(raw).decode("ascii")
        huge = "data:application/octet-stream;base64," + b64
        with self.assertRaises(ValueError):
            persist_connect_binary_from_data_url(1, {"data_url": huge})
