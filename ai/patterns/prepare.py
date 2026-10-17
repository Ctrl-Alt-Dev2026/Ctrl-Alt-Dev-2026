"""Explicit, local preparation. Importing the web app never downloads a model."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .corpus import build_corpus
from .engine import eligible

MODEL_ID = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
REVISION = 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
MODULE = Path(__file__).resolve().parent
REPOSITORY = MODULE.parents[1]


def prepare(data, output, model_path, revision=REVISION):
    if Path(output).resolve().is_relative_to(Path(data).resolve()):
        raise ValueError('Prepared output must not be written into the source fixture directory')
    from sentence_transformers import SentenceTransformer
    import sentence_transformers
    import torch
    corpus = build_corpus(Path(data))
    torch.set_num_threads(min(4, torch.get_num_threads()))
    # Local model only. Fetching weights is a separate, explicit setup action.
    model = SentenceTransformer(str(model_path), device='cpu', local_files_only=True,
                                trust_remote_code=False, token=False)
    texts = [e['profile'] for e in corpus['events']] + [e['source_profile'] for e in corpus['events']]
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=16).tolist()
    count = len(corpus['events'])
    eligible_vectors = [v for e, v in zip(corpus['events'], vectors) if eligible(e)]
    if not eligible_vectors:
        raise ValueError('No sufficiently described eligible synthetic events')
    center = [sum(v[j] for v in eligible_vectors)/len(eligible_vectors) for j in range(len(vectors[0]))]
    def centered(vector):
        delta = [v-c for v,c in zip(vector, center)]
        norm = math.sqrt(sum(v*v for v in delta))
        return [round(v/norm, 8) for v in delta] if norm else [0.0]*len(delta)
    corpus['vectors'] = {e['id']: centered(vector) for e, vector in zip(corpus['events'], vectors)}
    corpus['source_vectors'] = {e['id']: [round(v, 8) for v in vector] for e, vector in zip(corpus['events'], vectors[count:])}
    corpus['model'] = {'id': MODEL_ID, 'revision': revision, 'method': 'multilingual_sentence_embeddings',
                       'dimensions': len(vectors[0]), 'library': f'sentence-transformers {sentence_transformers.__version__}',
                       'device': 'cpu', 'license': 'Apache-2.0',
                       'transform': 'subtract eligible corpus mean, then L2 normalize; frozen during exclusions',
                       'centroid': center,
                       'profile_fields': ['reported cause', 'time context', 'explicitly associated crossing context'],
                       'excluded_fields': ['street names', 'coordinates', 'event IDs', 'dates', 'severity'],
                       'source': 'https://huggingface.co/' + MODEL_ID}
    lengths = [len(tokens) for tokens in model.tokenizer(texts, truncation=False)['input_ids']]
    corpus['model']['max_profile_tokens'] = max(lengths)
    corpus['model']['max_sequence_length'] = model.max_seq_length
    corpus['model']['truncated_profiles'] = sum(n > model.max_seq_length for n in lengths)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(corpus, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'output': str(output), 'model': {k:v for k,v in corpus['model'].items() if k!='centroid'}, 'coverage': corpus['coverage']}, ensure_ascii=False, indent=2))
    return corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=REPOSITORY / 'false_data')
    parser.add_argument('--output', type=Path, default=MODULE / 'data' / 'bundle.json')
    parser.add_argument('--model-path', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.data, args.output, args.model_path)


if __name__ == '__main__':
    main()
