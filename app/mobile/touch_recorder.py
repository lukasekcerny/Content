from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class RecordedAction:
    """A single user action captured from the emulator's input device."""
    type: str
    x: int
    y: int
    x2: int = -1
    y2: int = -1
    duration_ms: int = 100
    delay_after_ms: int = 500


@dataclass
class Recording:
    """A series of actions tied to a (platform, step) key."""
    key: str
    actions: list[RecordedAction] = field(default_factory=list)
    created_at: float = 0.0


class TouchRecorder:
    """Captures user touch events from an Android emulator via `adb shell getevent`.

    Parses the kernel input event stream for a single-touch (slot 0) sequence
    of taps and swipes, then exposes them as a list of ``RecordedAction``.

    Multi-touch (gestures with more than one finger) is collapsed to the first
    pointer; this is good enough for ordinary "tap a button" interactions.
    """

    def __init__(self, adb_path: str, device_id: str):
        self._adb = adb_path
        self._device_id = device_id
        self._proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._actions: list[RecordedAction] = []
        self._lock = threading.Lock()

        self._cur_x: int = -1
        self._cur_y: int = -1
        self._touching = False
        self._touch_start_x: int = -1
        self._touch_start_y: int = -1
        self._touch_start_time: float = 0.0
        self._last_event_end_time: Optional[float] = None

    def start(self) -> None:
        if self._proc is not None:
            return
        cmd = [self._adb, "-s", self._device_id, "shell", "getevent", "-lt"]
        logger.info("TouchRecorder starting: %s", " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as e:
            logger.exception("Failed to launch adb getevent")
            raise

        self._reader = threading.Thread(
            target=self._read_loop, name="TouchRecorderReader", daemon=True,
        )
        self._reader.start()

    def _read_loop(self) -> None:
        assert self._proc is not None
        assert self._proc.stdout is not None
        try:
            for line in iter(self._proc.stdout.readline, ""):
                if self._stop_flag.is_set():
                    break
                if not line:
                    break
                try:
                    self._parse_line(line.rstrip("\n"))
                except Exception:
                    logger.debug("Failed to parse getevent line: %r", line)
        except Exception:
            logger.exception("TouchRecorder read loop crashed")

    _RE_TIME = re.compile(r"\[\s*(\d+\.\d+)\s*\]")

    def _parse_line(self, line: str) -> None:
        m_time = self._RE_TIME.search(line)
        now = float(m_time.group(1)) if m_time else 0.0

        if "ABS_MT_POSITION_X" in line:
            self._cur_x = self._parse_hex_value(line)
            if self._touching and self._touch_start_x < 0:
                self._touch_start_x = self._cur_x
        elif "ABS_MT_POSITION_Y" in line:
            self._cur_y = self._parse_hex_value(line)
            if self._touching and self._touch_start_y < 0:
                self._touch_start_y = self._cur_y
        elif "ABS_MT_TRACKING_ID" in line:
            tid = self._parse_hex_value(line)
            if tid == 0xFFFFFFFF or tid == -1:
                if self._touching:
                    self._finalize_touch(now)
                self._touching = False
            else:
                self._touch_start_x = -1
                self._touch_start_y = -1
                self._touch_start_time = now
                self._touching = True

    @staticmethod
    def _parse_hex_value(line: str) -> int:
        try:
            tail = line.split()[-1]
            return int(tail, 16)
        except (ValueError, IndexError):
            return -1

    def _finalize_touch(self, now: float) -> None:
        if self._touch_start_x < 0 or self._touch_start_y < 0 or self._cur_x < 0 or self._cur_y < 0:
            return
        duration_ms = int(max(0.0, (now - self._touch_start_time) * 1000)) if now else 100
        if duration_ms <= 0:
            duration_ms = 100

        dx = self._cur_x - self._touch_start_x
        dy = self._cur_y - self._touch_start_y

        delay_after_ms = 800
        with self._lock:
            if self._actions and self._last_event_end_time and now:
                gap_ms = int((self._touch_start_time - self._last_event_end_time) * 1000)
                if gap_ms > 0:
                    self._actions[-1].delay_after_ms = max(200, min(gap_ms, 8000))

            if abs(dx) < 30 and abs(dy) < 30 and duration_ms < 600:
                action = RecordedAction(
                    type="tap",
                    x=self._touch_start_x,
                    y=self._touch_start_y,
                    duration_ms=duration_ms,
                    delay_after_ms=delay_after_ms,
                )
            else:
                action = RecordedAction(
                    type="swipe",
                    x=self._touch_start_x,
                    y=self._touch_start_y,
                    x2=self._cur_x,
                    y2=self._cur_y,
                    duration_ms=max(duration_ms, 100),
                    delay_after_ms=delay_after_ms,
                )
            self._actions.append(action)
            self._last_event_end_time = now
            logger.debug("Recorded action: %s", action)

        self._touch_start_x = -1
        self._touch_start_y = -1

    def stop(self) -> list[RecordedAction]:
        self._stop_flag.set()
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                logger.exception("Failed to terminate getevent process")
            try:
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if self._reader is not None:
            self._reader.join(timeout=2)
            self._reader = None

        with self._lock:
            actions = list(self._actions)
        logger.info("TouchRecorder stopped: %d actions captured", len(actions))
        return actions


def replay_actions(
    adb_path: str,
    device_id: str,
    actions: list[RecordedAction],
    status_cb=None,
) -> None:
    """Replay a list of recorded actions on the given device using `adb shell input`.

    Raises any subprocess error encountered so the caller can decide whether to
    re-record or fall back to the manual flow.
    """
    if not actions:
        return

    for i, a in enumerate(actions):
        if status_cb is not None:
            try:
                status_cb(f"Replay {i + 1}/{len(actions)}: {a.type} ({a.x},{a.y})", "info")
            except Exception:
                pass

        if a.type == "tap":
            cmd = [
                adb_path, "-s", device_id, "shell", "input", "tap",
                str(a.x), str(a.y),
            ]
        elif a.type == "swipe":
            cmd = [
                adb_path, "-s", device_id, "shell", "input", "swipe",
                str(a.x), str(a.y), str(a.x2), str(a.y2),
                str(max(a.duration_ms, 50)),
            ]
        else:
            logger.warning("Unknown action type during replay: %s", a.type)
            continue

        logger.info("Replay action %d/%d: %s", i + 1, len(actions), cmd[5:])
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=15,
            creationflags=_CREATE_NO_WINDOW,
        )

        delay_s = max(a.delay_after_ms, 200) / 1000.0
        time.sleep(min(delay_s, 6.0))


class RecordingStore:
    """Persists recordings to a JSON file in the app data directory.

    Schema: ``{ "<key>": { "key": str, "actions": [...], "created_at": float } }``

    Keys are typically of the form ``"<platform>:<step>"`` -- e.g.
    ``"instagram:set_profile_picture"`` -- so each step has at most one
    saved recording.
    """

    FILENAME = "recordings.json"

    def __init__(self, data_dir: str):
        self._path = os.path.join(data_dir, self.FILENAME)
        self._lock = threading.Lock()

    def _read(self) -> dict:
        if not os.path.isfile(self._path):
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except Exception:
            logger.exception("Failed to read %s", self._path)
            return {}

    def _write(self, data: dict) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            logger.exception("Failed to write %s", self._path)

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._read()

    def load(self, key: str) -> Optional[Recording]:
        with self._lock:
            data = self._read()
        entry = data.get(key)
        if not entry:
            return None
        try:
            actions = [RecordedAction(**a) for a in entry.get("actions", [])]
            return Recording(
                key=entry.get("key", key),
                actions=actions,
                created_at=float(entry.get("created_at", 0.0)),
            )
        except Exception:
            logger.exception("Failed to deserialize recording %s", key)
            return None

    def save(self, key: str, actions: list[RecordedAction]) -> None:
        rec = Recording(key=key, actions=actions, created_at=time.time())
        entry = {
            "key": rec.key,
            "actions": [asdict(a) for a in rec.actions],
            "created_at": rec.created_at,
        }
        with self._lock:
            data = self._read()
            data[key] = entry
            self._write(data)
        logger.info("Saved recording '%s' with %d actions", key, len(actions))

    def clear(self, key: str) -> None:
        with self._lock:
            data = self._read()
            if key in data:
                del data[key]
                self._write(data)
                logger.info("Cleared recording '%s'", key)

    def list_keys(self) -> list[str]:
        with self._lock:
            return list(self._read().keys())
