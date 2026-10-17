"""Explicit one-time download from the pinned official Hugging Face repository."""
import argparse
import os
from pathlib import Path

from .prepare import MODEL_ID, REVISION
from .service import DEFAULT_DATA, MODULE


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=MODULE/'work'/'model')
    args=parser.parse_args()
    output=args.output.resolve()
    if output.is_relative_to(DEFAULT_DATA.resolve()):
        raise ValueError('Model files must not be written into the source fixture directory')
    cache=MODULE/'work'/'hf'
    os.environ['HF_HOME']=str(cache)
    os.environ['TORCH_HOME']=str(MODULE/'work'/'torch')
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    from sentence_transformers import SentenceTransformer
    model=SentenceTransformer(MODEL_ID,revision=REVISION,cache_folder=str(cache),device='cpu',
                              trust_remote_code=False,token=False)
    model.save(str(output))
    print(f'Model saved: {output}')


if __name__=='__main__':main()
