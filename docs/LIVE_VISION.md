# Live camera detection

The Angular camera viewer plays the provider's HLS stream and sends sampled JPEG frames to the local FastAPI backend. Python runs **YOLO11s** for people, cars, buses, trucks, motorcycles and bicycles, plus **YOLO-World v2 small** with an embedded tram vocabulary. No TensorFlow or inference runs in the browser.

## Install and run

From the repository root, with Python 3.12:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-vision.txt
.venv\Scripts\python.exe -m safecross.live_setup
```

The setup downloads official Ultralytics checkpoints and the CLIP text encoder, prepares the tram vocabulary, tests both saved models, and records checkpoint hashes in `runtime/models/traffic-world.json`. All weights and caches stay under the ignored `runtime/` directory. CLIP is needed during setup; frame inference uses the saved vocabulary without downloading weights or encoding text. API startup and `/health` remain usable without these optional dependencies.

Start the existing backend and frontend as usual (`npm run backend`, then `npm start`, from `web/`). Enable **Camere live**, then open a camera marker. For lighting, choose **Marchează o trecere**, click 3–12 points around the crossing in order, and save. Up to eight polygons are remembered per camera in that browser. Redraw them if the camera's view changes. Without a marked crossing the UI reports image brightness only, with no claim about crosswalk lighting.

If an already-running backend predates this module, restart it: `/api/v1/vision/status` should return HTTP 200 with `available: true`. A generic 404 is a missing endpoint and produces a stable restart message. Only the explicit `vision_session_expired` and `stale_frame` errors recreate a session; a missing endpoint or session limit never enters an automatic loading loop. The first inference also includes model loading and can take tens of seconds on CPU.

Only one frame per viewer is in flight. Annotations are painted over the exact analysed sample, preventing boxes from drifting onto a newer video frame while the backend is working. The HUD identifies sampled frames, inference time and response time. Stopping detection restores continuous playback. Failed inference clears boxes and offers a retry; an unreadable HLS source falls back to the provider's player.

## Detection and limits

- Default: 1280-pixel inference, traffic confidence ≥0.35, people ≥0.50, open-vocabulary trams ≥0.50. A tram proposal replaces a strongly overlapping generic vehicle box.
- Dark images receive CLAHE contrast enhancement for detection only. Lighting is calculated from the **original** image using Rec.709 luma. A marked crossing is considered dark when its median is below 55/255 and at least 40% of its pixels are below 45/255. A warning needs three observations spanning at least two seconds, with a two-minute cooldown.
- Session-local tracking uses one-to-one class and geometry matching. Missing tracks expire after 2.5 seconds. A media gap over three seconds, a resolution change or detected camera displacement resets motion/contact evidence. IDs can change under occlusion; these are object tracks, not personal identities.
- **Possible incident** means persistent image overlap plus an observed vehicle slowdown and stop. It requires established tracks and multiple observations. **Prolonged stop** means a previously moving vehicle remained nearly stationary for 90 seconds. Both remain unvalidated operator signals. Neither rule confirms an accident or writes to the accident dataset.
- Live traffic, nighttime pedestrians, tram classification and crash alerts have not been validated on an annotated Iași dataset. Perspective, exposure, reflections, occlusion, crowds and sampling can cause misses and false alarms. Image luminance is not street illuminance in lux.

Environment overrides: `SAFEIASI_VISION_DEVICE=cpu` or `0` (CUDA), `SAFEIASI_VISION_IMGSZ=640|960|1280`, `SAFEIASI_VISION_MODEL` (prepared World checkpoint), `SAFEIASI_VISION_TRAFFIC_MODEL` (COCO-compatible YOLO traffic checkpoint). CUDA is selected automatically only when available in the installed PyTorch runtime. A lower image size trades small-object detail for throughput. Run one backend worker so sessions and the model stay in the same process.

The local API uses the existing loopback and same-origin guard. It does not fetch arbitrary stream URLs, retain submitted frames or create published accident records. Sessions expire after 120 seconds of inactivity; at most 16 exist. A frame is limited to 2 MiB and 1920×1080, checked before JPEG decoding. Inference is serialized; a busy detector returns 429 instead of queuing stale frames.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/vision/status` | Optional dependency and checkpoint readiness; no model load |
| POST | `/api/v1/vision/sessions` | `{camera_id, crosswalks: [{id, polygon: [[x,y], ...]}]}`; coordinates normalized to 0–1 |
| POST | `/api/v1/vision/sessions/{id}/frames?sequence=0&media_time=12.5` | Raw `image/jpeg`; increasing sequence and video timestamp; detections, lighting, signals, dimensions and timing |
| DELETE | `/api/v1/vision/sessions/{id}` | Release viewer tracking state |

All detection boxes are `[x, y, width, height]` in submitted-frame pixels. The response echoes frame identity. Configuration changes create a fresh session so old motion evidence cannot leak across views or crossing definitions. Upload limits, invalid frames, ordering conflicts, expired sessions and missing dependencies produce structured errors.

## Verification

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_live_vision.py -v
cd web
npm run build
```

The 17 automated fixtures exercise API boundaries, session expiry, one-to-one tracking, stopped/overlapping objects, synthetic incident motion, lighting persistence and crosswalk-specific measurements. They do not measure model accuracy. Another 44 existing API checks passed. Real inference was also checked on the official Ultralytics bus sample and night frames from Piața Unirii; the second public stream was unavailable at that check. A headless Chrome run verified live sampled annotations, crosswalk saving, pause/resume and desktop/mobile layouts without JavaScript errors. The final CPU run took approximately 1.2 seconds per sampled webcam frame; timing depends on load and hardware. Diagnostic images are local in `runtime/vision-check/`.

Upstream contracts: [YOLO11](https://docs.ultralytics.com/models/yolo11/), [YOLO-World vocabulary and offline model saving](https://docs.ultralytics.com/models/yolo-world/), [prediction and device settings](https://docs.ultralytics.com/modes/predict/). Ultralytics distributes its code/models under its AGPL-3.0/enterprise licensing options; see its [license terms](https://www.ultralytics.com/license).
