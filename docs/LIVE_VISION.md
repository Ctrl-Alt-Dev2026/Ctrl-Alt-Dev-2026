# Live camera detection

The Angular camera viewer plays the provider's HLS stream and sends sampled JPEG frames to the local FastAPI backend. Python runs **YOLO11s** for people, cars, buses, trucks, motorcycles and bicycles, plus **YOLO-World v2 small** with an embedded tram vocabulary. No TensorFlow or inference runs in the browser.

## Install and run

`npm run backend` (from `web/`) runs the API in Docker with all of this already installed and set up (CPU PyTorch,
no CUDA); nothing below is needed then. For `npm run backend:local`, from the repository root, with Python 3.12:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-vision.txt
.venv\Scripts\python.exe -m safecross.live_setup
```

The setup downloads official Ultralytics checkpoints and the CLIP text encoder, prepares the tram vocabulary, tests both saved models, and records checkpoint hashes in `runtime/models/traffic-world.json`. All weights and caches stay under the ignored `runtime/` directory. CLIP is needed during setup; frame inference uses the saved vocabulary without downloading weights or encoding text. API startup and `/health` remain usable without these optional dependencies.

Start the existing backend and frontend as usual (`npm run backend`, then `npm start`, from `web/`). Enable **Camere live**, then open a camera marker. For lighting, choose **Marchează o trecere**, click 3–12 points around the crossing in order, and save. Up to eight polygons are remembered per camera in that browser. Redraw them if the camera's view changes. Without a marked crossing the UI reports image brightness only, with no claim about crosswalk lighting.

If an already-running backend predates this module, restart it: `/api/v1/vision/status` should return HTTP 200 with `available: true`. A generic 404 is a missing endpoint and produces a stable restart message. Only the explicit `vision_session_expired` and `stale_frame` errors recreate a session; a missing endpoint or session limit never enters an automatic loading loop. The first inference also includes model loading and can take tens of seconds on CPU.

Only one frame per viewer is in flight. The default keeps continuous HLS playback and overlays the latest observations; boxes expire 1.5 seconds after their source video timestamp. They can lag moving objects by the inference delay. **Inspectează cadrele analizate** switches to exact frame/box alignment for inspection. Detection and playback are separate: a slow model no longer freezes video. The HUD shows inference and response time. Failed inference clears boxes and offers a retry; an unreadable HLS source falls back to the provider's player.

The background map's pulse repainting pauses while a camera is selected. Normal frame capture is limited to 1280×720; a focused detection region retains up to 1600×900 for distant-object detail. The displayed response time includes capture and JPEG encoding as well as the API call. No inference is sent while the tab is hidden.

**Zonă de detecție** lets the operator outline a road of interest. Inference crops to that region, maps boxes back to full-frame coordinates, and rejects objects whose bottom-centre lies outside the polygon. Focusing a narrow road keeps more detail on distant objects while excluding irrelevant buildings, statues and parked areas. **Analizează tot cadrul** removes the restriction. Regions are remembered per camera in that browser and need redrawing if the view changes. This is operator configuration, not automatic road recognition.

## Detection and limits

- Default: 960-pixel traffic inference, confidence ≥0.35, people ≥0.50. At most two detected buses/rail vehicles receive an additional 384-pixel cropped tram pass, with confidence ≥0.65 and overlap ≥0.40. The second model is loaded lazily and skipped entirely on other frames. An uncertain rail vehicle stays **vehicul feroviar**; tram proposals are marked with `?`. Full-frame inference remains available at 1280 through the environment override.
- Predictions below 0.80 need two observations before display; stronger ones appear immediately. This reduces transient boxes, not persistent false detections or missed objects. Worker threads apply their own PyTorch CPU thread limit to avoid oversubscription.
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
| POST | `/api/v1/vision/sessions` | `{camera_id, crosswalks: [{id, polygon: [[x,y], ...]}], detection_region?: {id, polygon}}`; coordinates normalized to 0–1 |
| POST | `/api/v1/vision/sessions/{id}/frames?sequence=0&media_time=12.5` | Raw `image/jpeg`; increasing sequence and video timestamp; detections, lighting, signals, dimensions and timing |
| DELETE | `/api/v1/vision/sessions/{id}` | Release viewer tracking state |

All detection boxes are `[x, y, width, height]` in submitted-frame pixels. The response echoes frame identity. Configuration changes create a fresh session so old motion evidence cannot leak across views or crossing definitions. Upload limits, invalid frames, ordering conflicts, expired sessions and missing dependencies produce structured errors.

## Verification

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_live_vision.py -v
cd web
npm run build
```

The 24 targeted fixtures cover API boundaries, session expiry, tracking, temporal confirmation, incident rules, lighting, detection-region cropping/coordinates and conditional tram inference. They do not measure model accuracy. The original integration also passed 44 existing API checks. Real inference was checked on the official Ultralytics bus sample and night frames from Piața Unirii. Browser checks cover continuous playback, exact-frame inspection, region saving and desktop/mobile layouts. Diagnostic images and timing results stay in `runtime/vision-check/`.

On the local AMD Ryzen 7 4800H CPU, isolated traffic inference measured 337 ms median at 1280 versus 201 ms at 960; the previous full-frame tram pass added 213 ms. The revised full frame-processing pipeline measured 271 ms median on a saved 1600×900 night frame after warmup. The final same-origin browser run processed 14 live frames with 426 ms median warm inference, including both full-frame and focused-region processing. It verified fresh visible annotations, continuous video, exact-frame inspection and region controls, with no JavaScript errors. Browser/video load, camera content, and optional tram candidates affect throughput. These timings are not accuracy or frame-rate guarantees. Establishing accuracy requires annotated daytime/nighttime camera clips and a held-out evaluation before fine-tuning or threshold changes; counting more boxes is not validation.

Upstream contracts: [YOLO11](https://docs.ultralytics.com/models/yolo11/), [YOLO-World vocabulary and offline model saving](https://docs.ultralytics.com/models/yolo-world/), [prediction and device settings](https://docs.ultralytics.com/modes/predict/). Ultralytics distributes its code/models under its AGPL-3.0/enterprise licensing options; see its [license terms](https://www.ultralytics.com/license).
