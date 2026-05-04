from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal, Slot

from app.mobile.emulator_config import (
    AndroidEmulatorConfig,
    EmulatorError,
    MobilePlatform,
    PlatformLaunchResult,
)
from app.mobile.emulator_controller import AndroidEmulatorController
from app.mobile.touch_recorder import (
    RecordingStore,
    TouchRecorder,
    replay_actions,
)

logger = logging.getLogger(__name__)


class ProfilePicPhoneWorker(QObject):
    """Background worker for changing profile picture (and bio) on each selected
    platform via the Android emulator.

    Per step (set_pp / set_bio) the flow is:
      1. If a saved recording exists for this (platform, step), REPLAY it and
         consider the step done. Skip the automated tap-by-text logic.
      2. Otherwise, run the controller's automated method.
      3. If the automated method raises, START a TouchRecorder, emit
         ``confirmation_needed`` so the GUI shows the Continue/Cancel dialog,
         and let the user finish the step manually in the emulator. When the
         user clicks Continue we stop the recorder and SAVE the captured
         actions under the step key, so next time we can replay them.

    The emulator is shut down only if every step on every platform succeeded
    (whether by automation or by replay; manual-only completions count as
    success too).
    """

    status_update = Signal(str, str)
    confirmation_needed = Signal(str, str)
    confirmation_received = Signal(bool)
    finished = Signal(list)

    def __init__(
        self,
        config: AndroidEmulatorConfig,
        platforms: list[MobilePlatform],
        image_path: str,
        bio: str = "",
        data_dir: Optional[str] = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._platforms = platforms
        self._image_path = image_path
        self._bio = bio or ""
        self._data_dir = data_dir
        self._store: Optional[RecordingStore] = (
            RecordingStore(data_dir) if data_dir else None
        )

        self._confirm_event = threading.Event()
        self._user_continue = False
        self.confirmation_received.connect(self._on_confirmation_received)

    @Slot(bool)
    def _on_confirmation_received(self, should_continue: bool) -> None:
        logger.info("PP worker received user decision: continue=%s", should_continue)
        self._user_continue = bool(should_continue)
        self._confirm_event.set()

    def _wait_for_user(self, label: str, reason: str) -> bool:
        self._confirm_event.clear()
        self._user_continue = False
        logger.info("PP worker emitting confirmation_needed for %s: %s", label, reason)
        self.confirmation_needed.emit(label, reason)
        self._confirm_event.wait()
        return self._user_continue

    def _run_step_with_record_replay(
        self,
        key: str,
        label: str,
        run_automation: Callable[[], None],
        adb_path: str,
        device_id: str,
    ) -> tuple[bool, bool, str]:
        """Run a single step with the record/replay machinery.

        Returns ``(succeeded, user_cancelled, message)``:
          - succeeded=True means the step is done (replay or automation or manual).
          - user_cancelled=True means the user clicked Cancel; the caller should stop.
        """
        if self._store is not None:
            recording = self._store.load(key)
            if recording and recording.actions:
                self.status_update.emit(
                    f"Replaying saved sequence for {label} ({len(recording.actions)} actions)...",
                    "info",
                )
                try:
                    replay_actions(
                        adb_path, device_id, recording.actions,
                        status_cb=self.status_update.emit,
                    )
                    msg = f"{label}: replayed saved recording ({len(recording.actions)} actions)."
                    self.status_update.emit(msg, "success")
                    return True, False, msg
                except Exception as e:
                    logger.exception("Replay failed for %s", key)
                    self.status_update.emit(
                        f"Replay of saved recording failed: {e}", "warning",
                    )

        try:
            run_automation()
            msg = f"{label}: automated step done."
            return True, False, msg
        except Exception as e:
            logger.exception("Automation failed for %s", key)
            self.status_update.emit(
                f"{label}: automated step failed: {e}", "error",
            )

        recorder: Optional[TouchRecorder] = None
        try:
            recorder = TouchRecorder(adb_path, device_id)
            recorder.start()
            self.status_update.emit(
                f"Recording your taps in the emulator for '{label}'. "
                f"Finish the step by hand, then click Continue.",
                "info",
            )
        except Exception as e:
            logger.exception("Failed to start TouchRecorder")
            self.status_update.emit(
                f"Could not start touch recorder: {e}. You can still finish manually.",
                "warning",
            )
            recorder = None

        should_continue = self._wait_for_user(
            label,
            "Automatický krok selhal. Doklikej to ručně v emulátoru – aplikace si "
            "tvoje akce nahrává a příště je přehraje.\n\nPo dokončení klikni Continue.",
        )

        captured: list = []
        if recorder is not None:
            try:
                captured = recorder.stop()
            except Exception:
                logger.exception("Failed to stop TouchRecorder")

        if captured and self._store is not None:
            try:
                self._store.save(key, captured)
                self.status_update.emit(
                    f"Saved {len(captured)} actions for '{key}' (will replay next time).",
                    "success",
                )
            except Exception:
                logger.exception("Failed to save recording for %s", key)

        if should_continue:
            return True, False, f"{label}: completed manually ({len(captured)} actions recorded)."
        return False, True, f"{label}: cancelled by user."

    def run(self):
        results: list[PlatformLaunchResult] = []
        controller: Optional[AndroidEmulatorController] = None
        device_id: Optional[str] = None
        all_success = False

        try:
            def _on_status(message: str, level: str) -> None:
                try:
                    self.status_update.emit(message, level)
                except Exception:
                    logger.exception("Failed to emit status_update")

            controller = AndroidEmulatorController(
                config=self._config,
                status_callback=_on_status,
            )

            try:
                device_id = controller.prepare_device()
            except EmulatorError as e:
                logger.error("Device preparation failed: %s", e)
                self.status_update.emit(str(e), "error")
                results = [
                    PlatformLaunchResult(platform=p, success=False, message=str(e))
                    for p in self._platforms
                ]
                return
            except Exception as e:
                logger.exception("Unexpected error preparing device")
                self.status_update.emit(f"Unexpected error: {e}", "error")
                results = [
                    PlatformLaunchResult(platform=p, success=False, message=str(e))
                    for p in self._platforms
                ]
                return

            if not self._image_path or not os.path.isfile(self._image_path):
                msg = f"Profile image file does not exist: {self._image_path}"
                logger.error(msg)
                self.status_update.emit(msg, "error")
                results = [
                    PlatformLaunchResult(platform=p, success=False, message=msg)
                    for p in self._platforms
                ]
                return

            image_filename = os.path.basename(self._image_path)
            try:
                controller.push_content_to_gallery(device_id, self._image_path)
            except Exception as e:
                logger.exception("Profile image push failed")
                self.status_update.emit(f"Gallery push failed: {e}", "error")
                should_continue = self._wait_for_user(
                    "Gallery push",
                    f"Nahrání obrázku do galerie selhalo: {e}",
                )
                if not should_continue:
                    self.status_update.emit(
                        "Profile flow cancelled by user.", "warning",
                    )
                    return

            try:
                adb_path = controller.resolve_adb_path()
            except Exception as e:
                logger.exception("adb path lost mid-run")
                self.status_update.emit(f"adb unavailable: {e}", "error")
                return

            for i, platform in enumerate(self._platforms):
                if i > 0:
                    time.sleep(2)

                step_failed = False

                try:
                    launch_result = controller.launch_platform(device_id, platform)
                except Exception as e:
                    logger.exception("Unhandled error launching %s", platform.display_name)
                    launch_result = PlatformLaunchResult(
                        platform=platform, success=False,
                        message=f"Launch error: {e}",
                    )
                if not launch_result.success:
                    step_failed = True
                    results.append(launch_result)
                    should_continue = self._wait_for_user(
                        platform.display_name,
                        launch_result.message or "Launch failed.",
                    )
                    if not should_continue:
                        self.status_update.emit(
                            "Profile flow cancelled by user. Emulator stays running.",
                            "warning",
                        )
                        return
                    continue

                pp_key = f"{platform.platform_id}:set_profile_picture"
                pp_label = f"{platform.display_name} - profile picture"

                pp_ok, pp_cancelled, pp_msg = self._run_step_with_record_replay(
                    key=pp_key,
                    label=pp_label,
                    run_automation=lambda: controller.set_profile_picture_in_app(
                        device_id, platform, image_filename,
                    ),
                    adb_path=adb_path,
                    device_id=device_id,
                )
                if pp_cancelled:
                    results.append(PlatformLaunchResult(
                        platform=platform, success=False, message=pp_msg,
                    ))
                    self.status_update.emit(
                        "Profile flow cancelled by user. Emulator stays running.",
                        "warning",
                    )
                    return
                if not pp_ok:
                    step_failed = True

                bio_msg = pp_msg
                if (
                    self._bio.strip()
                    and platform in (
                        MobilePlatform.INSTAGRAM,
                        MobilePlatform.TIKTOK,
                        MobilePlatform.YOUTUBE,
                    )
                ):
                    bio_key = f"{platform.platform_id}:set_bio"
                    bio_label = f"{platform.display_name} - bio"

                    bio_ok, bio_cancelled, bio_msg = self._run_step_with_record_replay(
                        key=bio_key,
                        label=bio_label,
                        run_automation=lambda: controller.set_bio_in_app(
                            device_id, platform, self._bio,
                        ),
                        adb_path=adb_path,
                        device_id=device_id,
                    )
                    if bio_cancelled:
                        results.append(PlatformLaunchResult(
                            platform=platform, success=False, message=bio_msg,
                        ))
                        self.status_update.emit(
                            "Profile flow cancelled by user. Emulator stays running.",
                            "warning",
                        )
                        return
                    if not bio_ok:
                        step_failed = True

                results.append(PlatformLaunchResult(
                    platform=platform,
                    success=not step_failed,
                    message=bio_msg or pp_msg,
                ))

            all_success = (
                len(results) == len(self._platforms)
                and all(r.success for r in results)
            )

            succeeded = sum(1 for r in results if r.success)
            failed = len(results) - succeeded
            summary = f"Profile flow done: {succeeded} succeeded, {failed} failed."
            level = "success" if failed == 0 else ("warning" if succeeded > 0 else "error")
            self.status_update.emit(summary, level)

        except Exception:
            logger.exception("Catastrophic failure in ProfilePicPhoneWorker.run")
        finally:
            if controller is not None and all_success:
                try:
                    controller.shutdown_emulator(device_id)
                except Exception:
                    logger.exception("shutdown_emulator failed")
            elif controller is not None:
                logger.info(
                    "Keeping emulator running (all_success=%s); user may continue manually",
                    all_success,
                )
                self.status_update.emit(
                    "Emulator left running so you can continue manually.",
                    "info",
                )
            try:
                self.finished.emit(results)
            except Exception:
                logger.exception("Failed to emit finished signal")
