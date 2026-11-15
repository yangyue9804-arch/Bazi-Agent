import hashlib
import json
import re
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bazi_resources import make_handler, search_classics


class ClassicsTests(unittest.TestCase):
    def test_manifest_integrity_and_transcription_status(self):
        manifest = json.loads((ROOT/'classics/manifest.json').read_text())
        self.assertEqual(len(manifest), 4)
        for book in manifest:
            raw = (ROOT/book['path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), book['file_sha256'])
            self.assertFalse(book['rules_approved'])
            self.assertGreater(book['body_characters'], 10000)

    def test_ziping_original_chapters_and_no_xu_commentary(self):
        text = (ROOT/'classics/zi_ping_zhen_quan_original.md').read_text()
        body = text.split('\n---\n', 1)[1]
        numbers = [int(v) for v in re.findall(r'^## (\d+) ', body, re.M)]
        self.assertEqual(numbers, list(range(1, 48)))
        self.assertNotIn('徐注：', body)

    def test_passages_match_citable_file_lines(self):
        result = search_classics('乙木', limit=4)
        self.assertGreater(result['total'], 0)
        for row in result['results']:
            lines = (ROOT/row['path']).read_text().splitlines()
            self.assertIn('乙木', row['text'])
            self.assertEqual(lines[row['line_start']-1], row['text'].splitlines()[0])
            self.assertTrue(row['chapter'])
        with self.assertRaises(ValueError):
            search_classics('  ')

    def test_http_passage_search(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(ROOT/'data/sources.json'))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            with urlopen(base+'/passages?q=%E4%B9%99%E6%9C%A8&limit=2') as response:
                result = json.load(response)
            self.assertEqual(len(result['results']), 2)
            self.assertEqual(result['kind'], 'classical_text_passages')
            with self.assertRaises(HTTPError) as error:
                urlopen(base+'/passages')
            self.assertEqual(error.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
