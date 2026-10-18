"""Prepare an offline traffic vocabulary, including trams, from official weights.

Run explicitly: python -m safecross.live_setup. Network is used only here.
"""

import hashlib
import json
import os
from pathlib import Path

from safecross.live_detector import MODEL_PATH, PROMPTS, ROOT, TRAFFIC_MODEL_PATH


def main():
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "runtime/ultralytics"))
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Keep both the downloaded weights and the CLIP cache inside the repository.
    os.environ.setdefault("TORCH_HOME", str(ROOT / "runtime/torch"))
    import clip
    import torch
    from ultralytics import YOLO, YOLOWorld, settings

    settings.update({"sync": False, "weights_dir": str(ROOT / "runtime/models"), "runs_dir": str(ROOT / "runtime/runs")})

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    original_load = clip.load

    def local_clip_load(name, *args, **kwargs):
        kwargs["download_root"] = str(ROOT / "runtime/clip")
        return original_load(name, *args, **kwargs)

    clip.load = local_clip_load
    try:
        traffic = YOLO(str(TRAFFIC_MODEL_PATH))
        model = YOLOWorld(str(MODEL_PATH.parent / "yolov8s-worldv2.pt"))
        model.set_classes(list(PROMPTS))
        temporary = MODEL_PATH.with_name("traffic-world.pending.pt")
        model.save(str(temporary))
        # Exercise the actual saved artifact before replacing an existing installation.
        import numpy as np
        saved = YOLOWorld(str(temporary))
        saved.predict(np.zeros((64, 64, 3), dtype=np.uint8), imgsz=640, device="cpu", verbose=False)
        traffic.predict(np.zeros((64, 64, 3), dtype=np.uint8), imgsz=640, device="cpu", verbose=False)
        temporary.replace(MODEL_PATH)
        manifest = {
            "source": "https://github.com/ultralytics/assets/releases", "checkpoint": "yolov8s-worldv2.pt",
            "prompts": list(PROMPTS), "sha256": hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),
            "ultralytics_version": __import__("ultralytics").__version__,
            "traffic_checkpoint": "yolo11s.pt", "traffic_sha256": hashlib.sha256(TRAFFIC_MODEL_PATH.read_bytes()).hexdigest(),
        }
        MODEL_PATH.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    finally:
        clip.load = original_load
    print(f"Offline live detector ready: {MODEL_PATH}")


if __name__ == "__main__":
    main()
