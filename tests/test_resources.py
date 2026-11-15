import io
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bazi_resources import (brave_search, canonical_url, make_handler, merge_sources,
                            search_sources, write_json)


class ResourceTests(unittest.TestCase):
    def test_canonical_preserves_episode(self):
        self.assertEqual(canonical_url("https://WWW.bilibili.com/video/BVtest/?p=2&utm_source=x#t"),
                         "https://www.bilibili.com/video/BVtest/?p=2")
        for value in ("file:///secret", "javascript:alert(1)", "https://a:b@example.com/"):
            with self.assertRaises(ValueError):
                canonical_url(value)

    def test_dedup_does_not_overwrite_review(self):
        original = [{"url": "https://example.com/a", "title": "人工标题",
                     "review_status": "reviewed", "rights_status": "permission_recorded",
                     "first_discovered_at": "old", "topics": ["classics"]}]
        found = [{"url": "https://example.com/a?utm_source=x", "title": "new",
                  "topics": ["career"], "queries": ["q"]}]
        rows = merge_sources(original, found * 2, "new")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "人工标题")
        self.assertEqual(rows[0]["review_status"], "reviewed")
        self.assertEqual(rows[0]["rights_status"], "permission_recorded")
        self.assertEqual(rows[0]["first_discovered_at"], "old")
        self.assertEqual(rows[0]["topics"], ["career", "classics"])

    def test_new_records_are_not_knowledge(self):
        rows = merge_sources([], [{"url": "https://example.com/", "title": "事业 八字"}], "now")
        self.assertEqual(rows[0]["review_status"], "candidate")
        self.assertFalse(rows[0]["content_ingested"])
        self.assertEqual(search_sources(rows, "事业")["total"], 1)
        self.assertEqual(search_sources(rows, status="reviewed")["total"], 0)
        self.assertEqual(search_sources(rows)["approved_knowledge_rules"], 0)

    def test_api_request_contract_without_network_or_key(self):
        def fake(request, timeout):
            self.assertEqual(request.get_header("X-subscription-token"), "test-only")
            self.assertIn("freshness=pm", request.full_url)
            self.assertEqual(timeout, 30)
            return io.BytesIO(json.dumps({"web": {"results": [{"url": "https://example.com"}]}}).encode())
        self.assertEqual(len(brave_search("八字", "test-only", "pm", opener=fake)), 1)

    def test_http_search_and_invalid_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "catalog.json"
            write_json(path, merge_sources([], [{"url": "https://example.com/", "title": "合婚"}], "now"))
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(path))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(base + "/search?q=%E5%90%88%E5%A9%9A") as response:
                    self.assertEqual(json.load(response)["total"], 1)
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + "/search?limit=bad")
                self.assertEqual(error.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
