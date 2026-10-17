"""Explicit, attributed CC BY-SA footage preparation; no synthetic road users."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4


SOURCE_PAGE = "https://commons.wikimedia.org/wiki/File:Roncesvalles_Ave_crossing_at_Galley_Ave,_PXO_Type_A_lights_flashing,_July_2026.webm"
DOWNLOAD_URL = "https://upload.wikimedia.org/wikipedia/commons/0/06/Roncesvalles_Ave_crossing_at_Galley_Ave%2C_PXO_Type_A_lights_flashing%2C_July_2026.webm"
SOURCE_SHA256 = "a16ca29b1458f98db39329810cd3d003f37c364061fe48bc69769fa2e515e3d1"
PREPARED_SHA256 = "3321ad7089441dafec8a5cd7da8dcaa185c310889d5319d0aa3bbd573007fae1"
DEFAULT_DIRECTORY = Path(__file__).resolve().parents[1] / "runtime" / "safecross-demo"
DEMO_ROI = [[.1, .42], [.7, .42], [.7, .63], [.1, .63]]
ATTRIBUTION = (
    "Qviri, Roncesvalles Ave / Galley Ave, Toronto, 15 July 2026, CC BY-SA 4.0. "
    "Not Iasi. Derived demonstration: first 12s, geometric virtual-tripod stabilization, "
    "720p, detail crop 640x360 at (400,300) then 1280x720, constant 30fps, audio omitted. "
    "Original handheld footage; stabilized view, no generated scenery or road users."
)


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_demo(directory=DEFAULT_DIRECTORY):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "roncesvalles-crossing.webm"
    clip = directory / "roncesvalles-crossing-detail-12s-cfr30.mp4"
    manifest = directory / "demo-manifest.json"
    recorded = None
    if manifest.exists():
        try:
            recorded = json.loads(manifest.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as error:
            raise ValueError("Existing demo manifest is not recognized; preserve it and choose another --directory.") from error
        if not isinstance(recorded, dict) or recorded.get("generator") != "safecross-demo-1" or recorded.get("source_sha256") != SOURCE_SHA256:
            raise ValueError("Existing demo manifest belongs to another source; choose another --directory.")
    if source.exists() and _hash(source) != SOURCE_SHA256:
        raise ValueError("Existing source hash differs; preserve it and choose another --directory.")
    if not source.exists():
        temporary = directory / (uuid4().hex + ".download")
        try:
            total = 0
            with urlopen(Request(DOWNLOAD_URL, headers={"User-Agent": "SafeIasi-demo/1.0"}), timeout=30) as response, temporary.open("xb") as output:
                while chunk := response.read(256 * 1024):
                    total += len(chunk)
                    if total > 12 * 1024 * 1024:
                        raise ValueError("Demo source exceeds expected size.")
                    output.write(chunk)
            if _hash(temporary) != SOURCE_SHA256:
                raise ValueError("Demo source hash mismatch; source was not installed.")
            temporary.replace(source)
        finally:
            temporary.unlink(missing_ok=True)
    reusable = clip.exists() and _hash(clip) == PREPARED_SHA256
    if clip.exists() and not reusable and recorded is not None:
        reusable = recorded.get("derived_sha256") == _hash(clip)
    if clip.exists() and not reusable:
        raise ValueError("Existing derived file is not this recorded demo; choose another --directory.")
    if not reusable:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise ValueError("Demo preparation needs local FFmpeg with vidstab filters; upload your own stable-view clip instead.")
        with tempfile.TemporaryDirectory(prefix="demo-render-", dir=directory) as working:
            owned = Path(working).resolve()
            if owned.parent != directory or not owned.name.startswith("demo-render-"):
                raise ValueError("Unexpected temporary directory.")
            common = [ffmpeg, "-nostdin", "-v", "error", "-i", str(source), "-t", "12"]
            commands = [
                common + ["-vf", "scale=1280:720,vidstabdetect=tripod=1:accuracy=9:result=motion.trf", "-an", "-f", "null", "-"],
                common + ["-vf", "scale=1280:720,vidstabtransform=input=motion.trf:tripod=1:optzoom=0:zoom=0:crop=black:interpol=bilinear,fps=30", "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-an", "-map_metadata", "-1", "-y", "full.mp4"],
                [ffmpeg, "-nostdin", "-v", "error", "-i", "full.mp4", "-vf", "crop=640:360:400:300,scale=1280:720,fps=30", "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-an", "-map_metadata", "-1", "-movflags", "+faststart", "-y", "detail.mp4"],
            ]
            for command in commands:
                result = subprocess.run(command, cwd=working, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if result.returncode:
                    raise ValueError("FFmpeg could not prepare the attributed demo; check local vidstab support.")
            (owned / "detail.mp4").replace(clip)
    metadata = {
        "generator": "safecross-demo-1", "source_page": SOURCE_PAGE, "download_url": DOWNLOAD_URL,
        "author": "Qviri", "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "source_sha256": SOURCE_SHA256, "derived_sha256": _hash(clip), "source_capture_date": "2026-07-15",
        "attribution": ATTRIBUTION, "data_mode": "observed", "location_label": "Toronto, Canada; not Iasi",
        "derived_file": clip.name, "roi": DEMO_ROI, "calibration": "uncalibrated",
    }
    manifest.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return clip, metadata


def submit_demo(clip, metadata, base_url="http://127.0.0.1:8000", operator="Demo SafeIasi", whole_frame=False):
    parsed = urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1", "::1") or parsed.username or parsed.password:
        raise ValueError("The demo can only be submitted to a local server.")
    fields = {
        "operator": operator, "data_mode": "observed", "fixed_camera_confirmed": "true",
        "source_url": SOURCE_PAGE, "attribution": metadata["attribution"],
        "license": metadata["license"] + " " + metadata["license_url"],
    }
    if not whole_frame:
        fields["roi_json"] = json.dumps(DEMO_ROI)
    boundary = "SafeCross" + uuid4().hex
    parts = []
    for key, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="video"; filename="{clip.name}"\r\nContent-Type: video/mp4\r\n\r\n'.encode())
    parts.extend([clip.read_bytes(), f"\r\n--{boundary}--\r\n".encode()])
    request = Request(base_url.rstrip("/") + "/api/v1/safecross/jobs", data=b"".join(parts), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urlopen(request, timeout=30) as response:
        job = json.load(response)
    return base_url.rstrip("/") + "/safecross?job=" + job["job_id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--submit", action="store_true", help="Upload the prepared clip to the local API; actual AI processing is queued")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--operator", default="Demo SafeIasi")
    parser.add_argument("--whole-frame", action="store_true", help="Omit the documented crossing ROI; expect perspective false positives")
    arguments = parser.parse_args()
    clip, metadata = prepare_demo(arguments.directory)
    print(submit_demo(clip, metadata, arguments.base_url, arguments.operator, arguments.whole_frame) if arguments.submit else json.dumps(metadata, ensure_ascii=True))


if __name__ == "__main__":
    main()
