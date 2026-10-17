"""Bounded local FFprobe preflight for the engine's frame_index / FPS clock.

The MVP accepts verified CFR inputs. A nominal/average FPS or monotonically
increasing timestamps alone do not establish that this clock follows playback.
https://ffmpeg.org/ffprobe.html
"""

from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

from safecross.detector import SafeCrossError


MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_DECODED_FRAMES = 120 * 120
PROBE_TIMEOUT_SECONDS = 20


def _probe_json(command: list[str], timeout: float, maximum_output_bytes: int) -> dict:
    """Drain both pipes with hard byte limits and terminate on overflow/timeout."""
    def read_bounded(stream, limit, process):
        content = stream.read(limit + 1)
        if len(content) > limit:
            try:
                process.kill()
            except OSError:
                pass
            raise SafeCrossError("video_timing_probe_output_limit", "FFprobe a depășit limita de ieșire; reexportă un clip CFR standard.")
        return content

    if timeout <= 0:
        raise SafeCrossError("video_timing_probe_timeout", "Verificarea timestampurilor a depășit limita de 20 de secunde.")
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
    except OSError as error:
        raise SafeCrossError("video_timing_probe_unavailable", "FFprobe nu poate fi pornit; verifică instalarea locală FFmpeg.") from error
    try:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="safecross-timing") as executor:
            output = executor.submit(read_bounded, process.stdout, maximum_output_bytes, process)
            errors = executor.submit(read_bounded, process.stderr, 16 * 1024, process)
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                process.kill()
                process.wait(timeout=3)
                raise SafeCrossError("video_timing_probe_timeout", "Verificarea timestampurilor a depășit limita de 20 de secunde.") from error
            stdout = output.result()
            errors.result()  # Check the stderr cap too; never expose raw file paths/logs.
        if process.returncode:
            raise SafeCrossError("video_timing_probe_failed", "FFprobe nu poate verifica filmarea; reexportă un clip CFR standard.")
        try:
            result = json.loads(stdout)
        except (ValueError, UnicodeError) as error:
            raise SafeCrossError("video_timing_invalid", "FFprobe a returnat metadate invalide pentru timestampuri.") from error
        if not isinstance(result, dict):
            raise SafeCrossError("video_timing_invalid", "FFprobe nu a returnat un obiect de metadate.")
        return result
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()


def _finite_number(value, field):
    if isinstance(value, bool):
        raise SafeCrossError("video_timing_invalid", f"Metadată video invalidă: {field}.")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as error:
        raise SafeCrossError("video_timing_invalid", f"Metadată video lipsă sau invalidă: {field}.") from error
    if not math.isfinite(result):
        raise SafeCrossError("video_timing_invalid", f"Metadată video nefinită: {field}.")
    return result


def _positive_fraction(value, field):
    try:
        if isinstance(value, bool):
            raise ValueError("Boolean is not a rate")
        result = Fraction(str(value))
        if result <= 0 or not math.isfinite(float(result)):
            raise ValueError("Nonpositive or unbounded rate")
        return result
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as error:
        raise SafeCrossError("video_timing_invalid", f"Metadată rațională video invalidă: {field}.") from error


def verify_video_timing(path: str | Path) -> dict:
    """Verify all decoded PTS against the nominal CFR clock, or fail closed.

    FFprobe is mandatory for this preflight; missing tooling never turns an
    unsupported/variable-rate source into a verified result. No source is edited.
    """
    deadline = time.monotonic() + PROBE_TIMEOUT_SECONDS
    source = Path(path)
    if not source.is_file():
        raise SafeCrossError("video_missing", "Fișierul video pentru verificarea timestampurilor nu există.")
    size = source.stat().st_size
    if size <= 0:
        raise SafeCrossError("video_empty", "Fișierul video este gol.")
    if size > MAX_UPLOAD_BYTES:
        raise SafeCrossError("video_too_large", "Verificarea video acceptă maximum 64 MiB.")
    executable = shutil.which("ffprobe")
    if not executable:
        raise SafeCrossError("ffprobe_missing", "FFprobe este necesar pentru verificarea CFR; instalează FFmpeg local și adaugă-l în PATH.")
    common = [executable, "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams", "v:0"]
    metadata = _probe_json(
        common + ["-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate,time_base,start_time,duration,nb_frames:format=duration", "-of", "json", str(source.resolve())],
        deadline - time.monotonic(), 64 * 1024,
    )
    streams = metadata.get("streams")
    if not isinstance(streams, list) or len(streams) != 1 or not isinstance(streams[0], dict):
        raise SafeCrossError("video_timing_invalid", "Nu există un flux video principal verificabil.")
    stream = streams[0]
    width, height = _finite_number(stream.get("width"), "width"), _finite_number(stream.get("height"), "height")
    if width != int(width) or height != int(height) or min(width, height) < 16 or max(width, height) > 4096 or width * height > 2_073_600:
        raise SafeCrossError("video_dimensions_unsupported", "Analiza acceptă maximum 2.073.600 pixeli per cadru și laturi de 16–4096 pixeli.")
    frame_rate = _positive_fraction(stream.get("avg_frame_rate"), "avg_frame_rate")
    fps = float(frame_rate)
    if not 1 <= fps <= 120:
        raise SafeCrossError("video_fps_unsupported", "Analiza acceptă FPS în intervalul 1–120.")
    time_base = _positive_fraction(stream.get("time_base"), "time_base")
    tolerance = max(2 * float(time_base), .001)
    if tolerance > max(.001, .1 / fps):
        raise SafeCrossError("video_timing_resolution_unsupported", "Precizia timestampurilor este insuficientă pentru verificarea CFR; reexportă un MP4 CFR cu timeline precis.")
    duration_value = stream.get("duration")
    if duration_value in (None, "N/A"):
        format_metadata = metadata.get("format", {})
        duration_value = format_metadata.get("duration") if isinstance(format_metadata, dict) else None
    duration = _finite_number(duration_value, "duration")
    if not 0 < duration <= 120.001:
        raise SafeCrossError("video_duration_unsupported", "Analiza acceptă un clip de maximum 120 de secunde.")
    frames_document = _probe_json(
        common + ["-read_intervals", "%+121", "-show_frames", "-show_entries", "frame=best_effort_timestamp_time", "-of", "json=compact=1", str(source.resolve())],
        deadline - time.monotonic(), 2 * 1024 * 1024,
    )
    frames = frames_document.get("frames")
    if not isinstance(frames, list) or not 2 <= len(frames) <= MAX_DECODED_FRAMES:
        raise SafeCrossError("video_timing_invalid", "Numărul de cadre verificabile trebuie să fie între 2 și 14.400.")
    timestamps = []
    for entry in frames:
        if not isinstance(entry, dict):
            raise SafeCrossError("video_timing_invalid", "FFprobe a returnat un cadru fără timestamp verificabil.")
        timestamps.append(_finite_number(entry.get("best_effort_timestamp_time"), "best_effort_timestamp_time"))
    first = timestamps[0]
    if abs(first) > tolerance:
        raise SafeCrossError("video_time_origin_unsupported", "Fluxul video nu începe la zero; reexportă un clip CFR cu timeline normalizat.")
    if any(current <= previous for previous, current in zip(timestamps, timestamps[1:])):
        raise SafeCrossError("video_timing_invalid", "Timestampurile nu sunt strict crescătoare; reexportă filmarea CFR.")
    maximum_error = max(abs(timestamp - first - index / fps) for index, timestamp in enumerate(timestamps))
    if maximum_error > tolerance:
        raise SafeCrossError("video_variable_fps", "Filmarea are timestampuri incompatibile cu FPS constant; reexportă CFR înainte de analiză.")
    decoded_duration = len(timestamps) / fps
    if decoded_duration > 120.001 or abs(decoded_duration - duration) > max(1 / fps, tolerance) + 1e-6:
        raise SafeCrossError("video_timing_duration_mismatch", "Timestampurile cadrelor nu corespund duratei declarate; reexportă filmarea CFR.")
    declared_count = stream.get("nb_frames")
    if declared_count not in (None, "N/A"):
        count = _finite_number(declared_count, "nb_frames")
        if count != int(count) or int(count) != len(timestamps):
            raise SafeCrossError("video_timing_frame_count_mismatch", "Numărul declarat de cadre diferă de cadrele verificate; analiza parțială nu este acceptată.")
    return {
        "validation": "ffprobe_cfr_verified", "tool": "ffprobe",
        "timestamp_field": "best_effort_timestamp_time", "fps": fps,
        "frame_rate": str(frame_rate), "time_base": str(time_base),
        "frame_count": len(timestamps), "first_pts_s": first, "last_pts_s": timestamps[-1],
        "max_error_s": maximum_error, "tolerance_s": tolerance,
        "declared_duration_s": duration, "decoded_duration_s": decoded_duration,
        "width": int(width), "height": int(height),
        "scope": "CFR verified within recorded tolerance; no traffic or calibration validation",
    }
