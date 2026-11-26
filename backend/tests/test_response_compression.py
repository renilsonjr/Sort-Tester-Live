"""Text answers go out compressed (owner report, 2026-11-26).

Opening the site cost 904 KB, most of it text served raw. The middleware
compresses what the browser says it accepts; what must not change is the
ask-before-reusing rule from #462 (ETags and 304s) and the hardening
headers on every answer.
"""
import unittest

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.tests.browser import BROWSER

GZ = {**BROWSER, "Accept-Encoding": "gzip"}


class CompressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app(), headers=GZ)

    def test_the_page_and_the_modules_go_out_compressed(self):
        for path in ("/", "/src/app.js", "/src/i18n.js"):
            with self.subTest(path=path):
                answer = self.client.get(path)
                self.assertEqual(answer.status_code, 200)
                self.assertEqual(answer.headers.get("content-encoding"), "gzip")
                # and much smaller than the file itself
                raw = int(answer.headers.get("content-length", "0"))
                self.assertLess(raw, len(answer.content))

    def test_a_browser_that_does_not_ask_gets_plain_bytes(self):
        plain = TestClient(create_app(), headers={**BROWSER, "Accept-Encoding": "identity"})
        answer = plain.get("/src/app.js")
        self.assertEqual(answer.status_code, 200)
        self.assertIsNone(answer.headers.get("content-encoding"))

    def test_the_ask_before_reusing_rule_still_stands(self):
        first = self.client.get("/src/app.js")
        self.assertEqual(first.headers.get("cache-control"), "no-cache")
        etag = first.headers["etag"]
        again = self.client.get("/src/app.js", headers={"If-None-Match": etag})
        self.assertEqual(again.status_code, 304)
        self.assertEqual(again.content, b"")

    def test_the_hardening_headers_survive_compression(self):
        answer = self.client.get("/")
        self.assertEqual(answer.headers.get("content-encoding"), "gzip")
        self.assertEqual(answer.headers.get("x-frame-options"), "DENY")
        self.assertIn("default-src 'self'", answer.headers.get("content-security-policy", ""))

    def test_health_still_answers_plainly_and_uncached(self):
        # Whether a tiny body is compressed is the middleware's business
        # (this stack compresses it); what must hold is the answer itself
        # and that nothing starts caching it.
        answer = self.client.get("/health")
        self.assertEqual(answer.status_code, 200)
        self.assertEqual(answer.json().get("status"), "ok")
        self.assertEqual(answer.headers.get("cache-control"), "no-store")


if __name__ == "__main__":
    unittest.main()
