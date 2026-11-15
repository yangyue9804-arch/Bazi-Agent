import copy
import json
import sys
import threading
import unittest
from collections import Counter
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bazi_resources import make_handler
from knowledge_tools import TOPICS,load_cards,search_cards,validate_cards


class KnowledgeTests(unittest.TestCase):
    def test_all_topics_and_source_citations(self):
        cards=load_cards()
        self.assertEqual(Counter(c['topic'] for c in cards),Counter({t:5 for t in TOPICS}))
        self.assertEqual(validate_cards(cards),[])
        self.assertTrue(all(c['sources'] and c['applicability']['exceptions'] for c in cards))

    def test_drafts_are_not_published(self):
        self.assertEqual(search_cards()['total'],0)
        result=search_cards(topic='compatibility',include_drafts=True)
        self.assertEqual(result['total'],5)
        self.assertEqual(result['approved_knowledge_rules'],0)
        self.assertTrue(all(c['evidence_relation']!='direct_text' for c in result['results']))

    def test_tampered_quote_is_rejected(self):
        cards=copy.deepcopy(load_cards())
        cards[0]['sources'][0]['quote']='不存在的古籍语句'
        self.assertTrue(any('Quotation not present' in e for e in validate_cards(cards)))

    def test_approval_without_expert_rejected(self):
        cards=copy.deepcopy(load_cards())
        cards[0]['review']['status']='approved'
        self.assertTrue(any('Approval requires' in e for e in validate_cards(cards)))

    def test_disagreements_keep_multiple_citations(self):
        cards=[c for c in load_cards() if c['evidence_relation']=='cross_text_conflict']
        self.assertGreaterEqual(len(cards),2)
        self.assertTrue(all(len({s['book_id'] for s in c['sources']})>=2 for c in cards))

    def test_http_explicit_draft_opt_in(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(ROOT/'data/sources.json'))
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            with urlopen(base+'/cards?topic=career') as response:
                self.assertEqual(json.load(response)['total'],0)
            with urlopen(base+'/cards?topic=career&include_drafts=true') as response:
                result=json.load(response)
            self.assertEqual(result['total'],5)
            self.assertFalse(result['results'][0]['review']['expert_reviewed'])
        finally:
            server.shutdown();server.server_close();worker.join(timeout=2)
