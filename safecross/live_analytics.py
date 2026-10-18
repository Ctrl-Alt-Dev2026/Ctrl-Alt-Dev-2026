"""Session-local image tracking and conservative operator signals, never accident records."""

from dataclasses import dataclass
import math


VEHICLES = {"car", "bus", "tram", "truck", "motorcycle", "bicycle"}


def center(box):
    return box[0] + box[2] / 2, box[1] + box[3] / 2


def intersection(a, b):
    return max(0., min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])) * max(0., min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))


def iou(a, b):
    common = intersection(a, b)
    return common / max(1., a[2] * a[3] + b[2] * b[3] - common)


@dataclass
class Track:
    id: int
    label: str
    box: list
    seen: float
    anchor: tuple
    still_since: float
    hits: int = 1
    speed: float = 0.
    last_moved: float = -math.inf
    abrupt_at: float = -math.inf


class Analytics:
    def __init__(self):
        self.tracks = {}
        self.next_id = 1
        self.contacts = {}
        self.dark_since = {}
        self.cooldowns = {}
        self.previous_time = None
        self.size = None
        self.previous_image = None

    def reset_tracks(self):
        self.tracks.clear()
        self.contacts.clear()
        self.dark_since.clear()

    def update(self, detections, frame, timestamp, crosswalks):
        import cv2
        import numpy as np

        height, width = frame.shape[:2]
        small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (128, 72)).astype(np.float32)
        gap = timestamp - self.previous_time if self.previous_time is not None else 0
        reset = self.size != (width, height) or gap > 3
        if not reset and self.previous_image is not None:
            shift, response = cv2.phaseCorrelate(self.previous_image, small)
            reset = response > .25 and math.hypot(*shift) > 4
        if reset:
            self.reset_tracks()
        self.previous_image, self.previous_time, self.size = small, timestamp, (width, height)
        self.tracks = {key: track for key, track in self.tracks.items() if timestamp - track.seen <= 2.5}
        self.cooldowns = {key: value for key, value in self.cooldowns.items() if timestamp - value < 600}
        current = self._associate(detections, timestamp)
        light = self._light(frame, crosswalks, detections)
        signals = self._incidents(current, timestamp)
        for region in light["crosswalks"]:
            key = f"light:{region['id']}"
            if region["low_light"]:
                since, hits = self.dark_since.get(key, (timestamp, 0))
                self.dark_since[key] = since, hits + 1
                if hits + 1 >= 3 and timestamp - since >= 2 and self._eligible(key, timestamp, 120):
                    signals.append(self._signal(key, "iluminat", "Trecere slab vizibilă — de verificat", "Luminozitate redusă persistentă în zona trecerii marcate; nu este o măsurare în lux.", [region["box"]]))
            else:
                self.dark_since.pop(key, None)
        return detections, light, signals, reset

    def _associate(self, detections, timestamp):
        # One-to-one global greedy association; a previous ID cannot match two detections.
        candidates = []
        for index, detection in enumerate(detections):
            for key, track in self.tracks.items():
                if track.label != detection["label"]:
                    continue
                box = detection["box"]
                distance = math.dist(center(box), center(track.box)) / max(8., math.hypot(track.box[2], track.box[3]))
                overlap = iou(box, track.box)
                if overlap >= .15 or distance < .65:
                    candidates.append((overlap - .2 * distance, index, key))
        assigned, used = {}, set()
        for _, index, key in sorted(candidates, reverse=True):
            if index not in assigned and key not in used:
                assigned[index] = key
                used.add(key)
        current = []
        for index, detection in enumerate(detections):
            box = detection["box"]
            track = self.tracks.get(assigned.get(index))
            if track is None:
                track = Track(self.next_id, detection["label"], box, timestamp, center(box), timestamp)
                self.next_id += 1
                self.tracks[track.id] = track
            else:
                dt = max(.05, timestamp - track.seen)
                diagonal = max(8., math.hypot(box[2], box[3]))
                speed = math.dist(center(box), center(track.box)) / diagonal / dt
                if track.speed > .35 and speed < .12 and track.hits >= 3:
                    track.abrupt_at = timestamp
                if math.dist(center(box), track.anchor) > .12 * diagonal:
                    track.anchor, track.still_since = center(box), timestamp
                    track.last_moved = timestamp
                track.speed, track.box, track.seen = speed, box, timestamp
                track.hits += 1
            detection["track_id"] = track.id
            current.append(track)
        return current

    def _eligible(self, key, timestamp, cooldown=60):
        if timestamp - self.cooldowns.get(key, -math.inf) < cooldown:
            return False
        self.cooldowns[key] = timestamp
        return True

    def _signal(self, key, kind, title, detail, boxes):
        return {"id": f"{key}:{self.previous_time:.3f}", "kind": kind, "title": title, "detail": detail, "boxes": boxes, "status": "needs_review"}

    def _incidents(self, current, timestamp):
        signals, contacts = [], {}
        reliable = [track for track in current if track.hits >= 3]
        for index, first in enumerate(reliable):
            for second in reliable[index + 1:]:
                if first.label not in VEHICLES and second.label not in VEHICLES:
                    continue
                common = intersection(first.box, second.box)
                smaller_area = min(first.box[2] * first.box[3], second.box[2] * second.box[3])
                if common / max(1., smaller_area) < .25:
                    continue
                key = f"incident:{min(first.id, second.id)}:{max(first.id, second.id)}"
                since = self.contacts.get(key, timestamp)
                contacts[key] = since
                stopped_after_motion = any(
                    track.label in VEHICLES and timestamp - track.abrupt_at < 5
                    and timestamp - track.still_since >= 1 and timestamp - track.last_moved < 6
                    for track in (first, second)
                )
                if timestamp - since >= 1.2 and stopped_after_motion and self._eligible(key, timestamp):
                    signals.append(self._signal(key, "incident", "Posibil incident — de verificat", "Suprapunere persistentă în imagine și oprire după mișcare. Perspectiva sau ocluzia pot produce un semnal fals; accidentul nu este confirmat.", [first.box, second.box]))
        self.contacts = contacts
        for track in reliable:
            if track.label in VEHICLES and math.isfinite(track.last_moved) and timestamp - track.still_since >= 90:
                key = f"stopped:{track.id}"
                if self._eligible(key, timestamp, 180):
                    signals.append(self._signal(key, "blocaj", "Vehicul oprit prelungit — de verificat", "Vehicul observat în mișcare, apoi aproape nemișcat cel puțin 90 s. Poate fi coadă, stație sau parcare; cauza este necunoscută.", [track.box]))
        return signals

    def _light(self, frame, crosswalks, detections):
        import cv2
        import numpy as np

        height, width = frame.shape[:2]
        # Rec.709 luma from the original BGR image, independent of detection enhancement.
        luma = frame[:, :, 2] * .2126 + frame[:, :, 1] * .7152 + frame[:, :, 0] * .0722
        cells = cv2.resize(luma.astype(np.float32), (16, 9), interpolation=cv2.INTER_AREA)
        mean = float(luma.mean())
        reports = []
        for region in crosswalks:
            polygon = np.array([[round(x * (width - 1)), round(y * (height - 1))] for x, y in region["polygon"]], dtype=np.int32)
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.fillPoly(mask, [polygon], 1)
            pixels = luma[mask == 1]
            if not pixels.size:
                continue
            median, dark_share = float(np.median(pixels)), float(np.mean(pixels < 45))
            x, y, w, h = cv2.boundingRect(polygon)
            people = sum(d["label"] == "person" and cv2.pointPolygonTest(polygon, (d["box"][0] + d["box"][2] / 2, min(height - 1., d["box"][1] + d["box"][3])), False) >= 0 for d in detections)
            reports.append({
                "id": region["id"], "polygon": region["polygon"], "box": [x, y, w, h],
                "median": round(median, 1), "darkShare": round(dark_share, 3),
                "low_light": median < 55 and dark_share >= .4, "people": people,
            })
        return {
            "mean": round(mean, 1), "darkShare": round(float(np.mean(cells < 35)), 3),
            "cells": cells.ravel().round(1).tolist(), "level": "slabă" if mean < 55 else "medie" if mean < 100 else "bună",
            "crosswalks": reports, "measurement": "image_luminance_not_lux",
        }
