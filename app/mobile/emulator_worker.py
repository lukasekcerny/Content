from __future__ import annotations

import logging
import threading
import time

from PySide6.QtCore import QObject, Signal, Slot

from app.mobile.emulator_config import (
    AndroidEmulatorConfig,
    EmulatorError,
    MobilePlatform,
    PlatformLaunchResult,
)
from app.mobile.emulator_controller import AndroidEmulatorController

logger = logging.getLogger(__name__)


class EmulatorWorker(QObject):
    """Background worker that drives the AndroidEmulatorController.

    Designed to be moved to a QThread via moveToThread(). The worker
    orchestrates the per-platform launch loop itself so it can pause on
    failure and wait for a user decision from the GUI thread.

    Signals:
      - status_update(message, level): progress for the activity log.
      - confirmation_needed(platform_display, reason): emitted when a platform
        (or gallery push) failed. The GUI should show a modal and then emit
        `confirmation_received(bool)` back with Continue=True / Cancel=False.
      - confirmation_received(bool): the GUI -> worker channel. The worker
        blocks on an internal Event until this is fired.
      - finished(list[PlatformLaunchResult]): emitted exactly once when done.
    """

    status_update = Signal(str, str)
    confirmation_needed = Signal(str, str)
    confirmation_received = Signal(bool)
    finished = Signal(list)

    def __init__(
        self,
        config: AndroidEmulatorConfig,
        platforms: list[MobilePlatform],
        content_file_path: str | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._platforms = platforms
        self._content_file_path = content_file_path

        self._confirm_event = threading.Event()
        self._user_continue = False

        self.confirmation_received.connect(self._on_confirmation_received)

    @Slot(bool)
    def _on_confirmation_received(self, should_continue: bool) -> None:
        logger.info("Worker received user decision: continue=%s", should_continue)
        self._user_continue = bool(should_continue)
        self._confirm_event.set()

    def _wait_for_user(self, platform_display: str, reason: str) -> bool:
        """Emit confirmation_needed and block until GUI responds. Returns True to continue."""
        self._confirm_event.clear()
        self._user_continue = False
        logger.info(
            "Worker emitting confirmation_needed for %s: %s", platform_display, reason
        )
        self.confirmation_needed.emit(platform_display, reason)
        self._confirm_event.wait()
        return self._user_continue

    def run(self):
        results: list[PlatformLaunchResult] = []
        controller: AndroidEmulatorController | None = None
        device_id: str | None = None
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

            if self._content_file_path:
                try:
                    controller.push_content_to_gallery(device_id, self._content_file_path)
                except Exception as e:
                    logger.exception("Content push failed")
                    self.status_update.emit(f"Gallery push failed: {e}", "error")
                    should_continue = self._wait_for_user(
                        "Gallery push",
                        f"Nahrání souboru do galerie selhalo: {e}",
                    )
                    if not should_continue:
                        results = []
                        self.status_update.emit("Flow cancelled by user.", "warning")
                        return

            for i, platform in enumerate(self._platforms):
                if i > 0:
                    time.sleep(2)

                try:
                    result = controller.launch_platform(device_id, platform)
                except Exception as e:
                    logger.exception("Unhandled error launching %s", platform.display_name)
                    self.status_update.emit(
                        f"{platform.display_name}: unhandled error ({e})", "error"
                    )
                    result = PlatformLaunchResult(
                        platform=platform,
                        success=False,
                        message=f"Unhandled error: {e}",
                    )

                results.append(result)

                if not result.success:
                    should_continue = self._wait_for_user(
                        platform.display_name,
                        result.message or "Platforma selhala.",
                    )
                    if not should_continue:
                        self.status_update.emit(
                            "Flow cancelled by user. Emulator stays running.",
                            "warning",
                        )
                        return

            all_success = all(r.success for r in results) and len(results) == len(self._platforms)

            succeeded = sum(1 for r in results if r.success)
            failed = len(results) - succeeded
            summary = f"Done: {succeeded} opened, {failed} failed."
            level = "success" if failed == 0 else ("warning" if succeeded > 0 else "error")
            self.status_update.emit(summary, level)

        except Exception:
            logger.exception("Catastrophic failure in EmulatorWorker.run")
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
