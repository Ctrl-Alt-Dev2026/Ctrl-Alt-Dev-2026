"""`npm run ai`: the Claude step (isu/ai.py) on this laptop, through Claude Code and your claude.ai login.

    python web/scripts/ai.py [--articole] [--strazi] [--limita N] [--paralel 4] [--refa]

Classifies and extracts the scraped press articles, suggests what to study on each street, rebuilds the dataset
and rewrites isu/seed/ (answers in isu/seed/ai/): commit it and colleagues and Docker replay the answers.
Needs Claude Code installed and logged in (`claude` in PATH). Uses the repo's .venv, like `npm run backend:local`.
"""
import os
import subprocess
import sys

from backend import PYTHON, ROOT, ensure_venv

if __name__ == "__main__":
    ensure_venv()
    sys.exit(subprocess.run([str(PYTHON), "-m", "isu.ai", *sys.argv[1:]], cwd=ROOT,
                            env={**os.environ, "PYTHONUTF8": "1"}).returncode)
