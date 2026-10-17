"""Authored development probes: semantic retrieval vs a lexical baseline.

These are deliberately small engineering probes, NOT a benchmark of real safety conclusions.
"""
import argparse
import copy
import json
import math
from pathlib import Path

from .engine import cosine, discover, eligible
from .service import PatternService

PROBES = [
    ('ro_speed', 'Mașina ar fi mers mult prea repede.', ['ev-001','ev-003','ev-007','ev-014']),
    ('en_speed', 'A motorist was driving much too fast.', ['ev-001','ev-003','ev-007','ev-014']),
    ('it_speed', 'La macchina procedeva a velocità eccessiva.', ['ev-001','ev-003','ev-007','ev-014']),
    ('ro_visibility', 'Șoferului i-a fost greu să vadă pietonul în întuneric.', ['ev-010']),
    ('en_visibility', 'Poor visibility at night: the driver did not see the person crossing.', ['ev-010']),
    ('ro_yield', 'Conducătorul nu a lăsat pietonul să treacă primul.', ['ev-005','ev-009']),
    ('en_yield', 'The motorist failed to give way to someone crossing.', ['ev-005','ev-009']),
    ('ro_crossing', 'Pietonul a traversat printr-un loc nepermis.', ['ev-002','ev-008']),
    ('en_crossing', 'A pedestrian crossed where crossing was not permitted.', ['ev-002','ev-008']),
    ('en_school', 'A school close to an unsignalized crossing over two lanes.', ['ev-008','ev-009']),
]


def evaluate(model_path, output):
    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import TfidfVectorizer
    import torch
    torch.set_num_threads(4)
    bundle = PatternService().load()
    events = [e for e in bundle['events'] if eligible(e)]
    ids = [e['id'] for e in events]
    model = SentenceTransformer(str(model_path), device='cpu', local_files_only=True, trust_remote_code=False, token=False)
    encoded = model.encode([p[1] for p in PROBES], normalize_embeddings=True, show_progress_bar=False)
    centroid = bundle['model']['centroid']
    queries = [[float(v)-c for v,c in zip(vector,centroid)] for vector in encoded]
    lexical = TfidfVectorizer(strip_accents='unicode', ngram_range=(1,2))
    matrix = lexical.fit_transform([e['profile'] for e in events])
    lexical_queries = lexical.transform([p[1] for p in PROBES])
    scores = (lexical_queries @ matrix.T).toarray()
    rows = []
    for index, (name, query, expected) in enumerate(PROBES):
        semantic = sorted(ids, key=lambda i: (-cosine(queries[index],bundle['vectors'][i]),i))
        # Zero lexical overlap is abstention, not an arbitrary first-record hit.
        baseline = [ids[i] for i in sorted(range(len(ids)),key=lambda i:(-scores[index][i],ids[i])) if scores[index][i]>0]
        row = {'id':name,'query':query,'expected_ids':expected,'embedding_top3':semantic[:3], 'tfidf_top3':baseline[:3]}
        for method, ranking in [('embedding',semantic),('tfidf',baseline)]:
            row[method+'_hit1'] = bool(ranking and ranking[0] in expected)
            row[method+'_reciprocal_rank'] = next((1/(n+1) for n,i in enumerate(ranking) if i in expected),0)
        rows.append(row)
    baseline_bundle = copy.deepcopy(bundle)
    baseline_bundle['vectors'] = {e['id']:matrix[ids.index(e['id'])].toarray()[0].tolist() if e['id'] in ids else [0.0]*matrix.shape[1] for e in bundle['events']}
    baseline_bundle['model']['method']='tfidf_lexical_baseline'
    result = {'label':'Authored development probes on synthetic fixtures; not a real-world validity study',
              'input_sha256':bundle['input_sha256'], 'probe_count':len(rows),
              'method':bundle['model']['id'], 'revision':bundle['model']['revision'],
              'summary':{m:{'hit_at_1':sum(r[m+'_hit1'] for r in rows)/len(rows),
                             'mrr':sum(r[m+'_reciprocal_rank'] for r in rows)/len(rows)} for m in ['embedding','tfidf']},
              'probes':rows,
              'embedding_patterns':discover(bundle),
              'tfidf_patterns_same_exploratory_threshold':discover(baseline_bundle),
              'limitations':['Queries authored after inspecting fixture schema; development only.',
                             'Lexical baseline is intentionally simple and not tuned.',
                             'A shared threshold is not a calibrated comparison of clustering quality.',
                             'No human-labelled cluster ground truth or causality evaluation exists.',
                             'No traffic or pedestrian exposure denominators are provided.']}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-path',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'evaluation'/'semantic_probes.json')
    args=parser.parse_args()
    evaluate(args.model_path,args.output)
