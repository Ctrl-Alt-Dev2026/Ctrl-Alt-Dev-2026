"""Explicit, bounded installation of the pinned official YOLOX Nano checkpoint."""

import hashlib
from pathlib import Path
import tempfile
from urllib.request import urlopen


MODEL_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx"
MODEL_SHA256 = "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d"
MODEL_PATH = Path(__file__).resolve().parents[1] / "runtime" / "models" / "yolox_nano.onnx"


def install_model(path=MODEL_PATH):
    path = Path(path).resolve()
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == MODEL_SHA256:
        return path
    if path.exists():
        raise ValueError("Existing model has another hash; preserve it and select a new destination.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="yolox-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            digest, total = hashlib.sha256(), 0
            with urlopen(MODEL_URL, timeout=30) as response:
                while chunk := response.read(256 * 1024):
                    total += len(chunk)
                    if total > 8 * 1024 * 1024:
                        raise ValueError("Checkpoint exceeds expected download limit.")
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != MODEL_SHA256:
                raise ValueError("Checkpoint hash mismatch; downloaded file was not installed.")
        temporary.replace(path)
        return path
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    installed = install_model()
    print(f"YOLOX Nano ONNX ready: {installed.name}; sha256={MODEL_SHA256}")
