"""Validate and retrieve citable knowledge-card drafts. No LLM or predictive engine."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TOPICS=('career','love','family','wealth','children','timing','compatibility')
TYPES={'classical_method','historical_convention','textual_disagreement',
       'editorial_workflow','product_boundary'}
RELATIONS={'direct_text','editorial_application','cross_text_conflict','evidence_gap'}


def load_cards(root=ROOT):
    return [card for topic in TOPICS
            for card in json.loads((Path(root)/'knowledge'/f'{topic}.json').read_text())]


def validate_cards(cards, root=ROOT):
    errors=[]
    seen=set()
    required={'schema_version','id','version','topic','title','card_type','evidence_relation',
              'principle','sources','applicability','interpretation','evaluation_examples',
              'related_cards','review','source_quality_flags','license'}
    for card in cards:
        name=card.get('id','<missing id>')
        def fail(message):
            errors.append(f'{name}: {message}')
        if missing:=required-card.keys():
            fail('Missing fields '+str(sorted(missing)))
            continue
        if name in seen:
            fail('Duplicate ID')
        seen.add(name)
        if card['topic'] not in TOPICS or card['card_type'] not in TYPES:
            fail('Invalid topic or card type')
        if card['evidence_relation'] not in RELATIONS:
            fail('Invalid evidence relation')
        review=card['review']
        if review.get('status') not in {'draft','approved','rejected'}:
            fail('Invalid review status')
        if review.get('status')=='approved':
            if not all([review.get('expert_reviewed'),review.get('reviewer'),
                        review.get('reviewed_at'),review.get('publication_eligible')]):
                fail('Approval requires named expert review, timestamp and publication eligibility')
        elif review.get('publication_eligible'):
            fail('Unapproved card cannot be publication eligible')
        if card['applicability'].get('auto_applicable'):
            fail('This release does not implement executable applicability rules')
        if card['interpretation'].get('reflection_is_classical_claim'):
            fail('Modern reflections must be separate from classical claims')
        if not card['sources']:
            fail('Missing sources')
        if card['evidence_relation']=='cross_text_conflict' and len(card['sources'])<2:
            fail('A textual conflict needs at least two citations')
        for source in card['sources']:
            path=Path(root)/source['repository_path']
            if not path.resolve().is_relative_to((Path(root)/'classics').resolve()):
                fail('Citation outside classics directory')
                continue
            if not path.is_file():
                fail('Missing cited file')
                continue
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=source['file_sha256']:
                fail('Source file checksum mismatch')
            text=raw.decode('utf-8')
            lines=text.splitlines()
            start,end=source['line_start'],source['line_end']
            if not (1<=start<=end<=len(lines)):
                fail('Invalid citation line range')
                continue
            if not source['quote'] or source['quote'] not in '\n'.join(lines[start-1:end]):
                fail('Quotation not present at cited lines')
            before='\n'.join(lines[:start])
            if source['chapter'] not in before:
                fail('Chapter not found before quoted lines')
    for card in cards:
        for related in card.get('related_cards',[]):
            if related not in seen:
                errors.append(f"{card.get('id')}: Unknown related card {related}")
    return errors


def search_cards(q='', topic=None, include_drafts=False, limit=20, root=ROOT):
    if topic is not None and topic not in TOPICS:
        raise ValueError('Unknown topic')
    cards=load_cards(root)
    errors=validate_cards(cards,root)
    if errors:
        raise ValueError('Knowledge validation failed; run knowledge_tools.py validate')
    terms=q.casefold().split()
    hits=[]
    for card in cards:
        if topic and card['topic']!=topic:
            continue
        review=card['review']
        ready=review['status']=='approved' and review['expert_reviewed'] and review['publication_eligible']
        if not ready and not (include_drafts and review['status']=='draft'):
            continue
        searchable=json.dumps({k:card[k] for k in ('id','title','topic_label','principle','interpretation','sources')},
                              ensure_ascii=False).casefold()
        if not terms or all(term in searchable for term in terms):
            hits.append(card)
    return {'kind':'bazi_knowledge_cards','total':len(hits),'results':hits[:max(1,min(int(limit),100))],
            'include_drafts':include_drafts,
            'approved_knowledge_rules':sum(c['review']['status']=='approved' and c['review']['expert_reviewed']
                                           and c['review']['publication_eligible'] for c in cards),
            'notice':'Drafts are for editorial review only. Text citations do not validate personal predictions.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('validate')
    search=sub.add_parser('search')
    search.add_argument('query',nargs='?',default='')
    search.add_argument('--topic',choices=TOPICS)
    search.add_argument('--include-drafts',action='store_true')
    args=parser.parse_args()
    if args.command=='validate':
        cards=load_cards();errors=validate_cards(cards)
        print(json.dumps({'cards':len(cards),'errors':errors},ensure_ascii=False,indent=2))
        return 1 if errors else 0
    print(json.dumps(search_cards(args.query,args.topic,args.include_drafts),ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
