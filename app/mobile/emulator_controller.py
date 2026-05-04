from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from typing import Callable, Optional

from app.mobile.emulator_config import (
    AndroidDeviceInfo,
    AndroidEmulatorConfig,
    AdbNotFoundError,
    DeviceNotFoundError,
    DeviceSelectionError,
    EmulatorBootTimeoutError,
    EmulatorNotFoundError,
    EmulatorStartError,
    MobilePlatform,
    PackageLaunchError,
    PackageNotInstalledError,
    PlatformLaunchResult,
)

logger = logging.getLogger(__name__)

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class AndroidEmulatorController:
    """Orchestrates ADB commands and emulator lifecycle.

    Pure business logic -- no PySide6 dependencies. All long-running work
    happens synchronously; the caller (EmulatorWorker) is responsible for
    running this off the GUI thread.
    """

    def __init__(
        self,
        config: AndroidEmulatorConfig,
        status_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self._config = config
        self._status = status_callback or (lambda msg, lvl: None)
        self._adb: Optional[str] = None
        self._emulator: Optional[str] = None
        self._emulator_proc: Optional[subprocess.Popen] = None
        self._we_started_emulator: bool = False

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def resolve_adb_path(self) -> str:
        if self._adb:
            return self._adb

        if self._config.adb_path and os.path.isfile(self._config.adb_path):
            self._adb = self._config.adb_path
            return self._adb

        found = shutil.which("adb")
        if found:
            self._adb = found
            return self._adb

        for env_var in ("LOCALAPPDATA", "ANDROID_HOME", "ANDROID_SDK_ROOT"):
            base = os.environ.get(env_var)
            if not base:
                continue
            if env_var == "LOCALAPPDATA":
                candidate = os.path.join(base, "Android", "Sdk", "platform-tools", "adb.exe")
            else:
                candidate = os.path.join(base, "platform-tools", "adb.exe")
            if os.path.isfile(candidate):
                self._adb = candidate
                return self._adb

        raise AdbNotFoundError(
            "adb.exe not found. Install Android SDK or set adb_path in config. "
            "Searched: explicit config, PATH, LOCALAPPDATA/Android/Sdk, ANDROID_HOME, ANDROID_SDK_ROOT."
        )

    def resolve_emulator_path(self) -> str:
        if self._emulator:
            return self._emulator

        if self._config.emulator_path and os.path.isfile(self._config.emulator_path):
            self._emulator = self._config.emulator_path
            return self._emulator

        found = shutil.which("emulator")
        if found:
            self._emulator = found
            return self._emulator

        for env_var in ("LOCALAPPDATA", "ANDROID_HOME", "ANDROID_SDK_ROOT"):
            base = os.environ.get(env_var)
            if not base:
                continue
            if env_var == "LOCALAPPDATA":
                candidate = os.path.join(base, "Android", "Sdk", "emulator", "emulator.exe")
            else:
                candidate = os.path.join(base, "emulator", "emulator.exe")
            if os.path.isfile(candidate):
                self._emulator = candidate
                return self._emulator

        raise EmulatorNotFoundError(
            "emulator.exe not found. Install Android SDK or set emulator_path in config. "
            "Searched: explicit config, PATH, LOCALAPPDATA/Android/Sdk, ANDROID_HOME, ANDROID_SDK_ROOT."
        )

    # ------------------------------------------------------------------
    # Device enumeration
    # ------------------------------------------------------------------

    def list_devices(self) -> list[AndroidDeviceInfo]:
        adb = self.resolve_adb_path()
        result = self._run_adb([adb, "devices"])
        return self.parse_devices_output(result.stdout)

    @staticmethod
    def parse_devices_output(output: str) -> list[AndroidDeviceInfo]:
        devices: list[AndroidDeviceInfo] = []
        for line in output.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                devices.append(AndroidDeviceInfo(serial=parts[0], state=parts[1]))
        return devices

    def select_device(self, devices: list[AndroidDeviceInfo]) -> str:
        online = [d for d in devices if d.state == "device"]

        if self._config.device_id:
            matching = [d for d in online if d.serial == self._config.device_id]
            if matching:
                return matching[0].serial
            all_matching = [d for d in devices if d.serial == self._config.device_id]
            if all_matching:
                raise DeviceNotFoundError(
                    f"Device {self._config.device_id} found but state is "
                    f"'{all_matching[0].state}' (expected 'device')."
                )
            raise DeviceNotFoundError(
                f"Configured device_id '{self._config.device_id}' not found in connected devices. "
                f"Available: {[d.serial for d in devices]}"
            )

        if len(online) == 1:
            return online[0].serial

        if len(online) == 0:
            raise DeviceNotFoundError("No online ADB devices found.")

        raise DeviceSelectionError(
            f"Multiple devices connected ({[d.serial for d in online]}) but no device_id is configured. "
            f"Set device_id in emulator config to select which device to use."
        )

    # ------------------------------------------------------------------
    # Device boot status
    # ------------------------------------------------------------------

    def is_device_booted(self, device_id: str) -> bool:
        adb = self.resolve_adb_path()
        try:
            result = self._run_adb(
                [adb, "-s", device_id, "shell", "getprop", "sys.boot_completed"],
                timeout=10,
            )
            return result.stdout.strip() == "1"
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False

    def wait_for_device(self, device_id: str, timeout: Optional[int] = None) -> bool:
        timeout = timeout or self._config.startup_timeout_seconds
        deadline = time.time() + timeout
        poll_interval = 3

        logger.info("Waiting for device %s to boot (timeout=%ds)", device_id, timeout)
        self._status(f"Waiting for device {device_id} to boot...", "info")

        while time.time() < deadline:
            if self.is_device_booted(device_id):
                logger.info("Device %s boot complete", device_id)
                self._status(f"Device {device_id} is ready.", "success")
                return True
            time.sleep(poll_interval)

        raise EmulatorBootTimeoutError(
            f"Device {device_id} did not finish booting within {timeout}s."
        )

    # ------------------------------------------------------------------
    # Emulator lifecycle
    # ------------------------------------------------------------------

    def list_avds(self) -> list[str]:
        try:
            emulator = self.resolve_emulator_path()
        except EmulatorNotFoundError:
            return []
        try:
            result = subprocess.run(
                [emulator, "-list-avds"],
                capture_output=True, text=True,
                timeout=self._config.command_timeout_seconds,
                creationflags=_CREATE_NO_WINDOW,
            )
            avds = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
            return avds
        except Exception:
            return []

    def start_emulator_if_needed(self) -> str:
        devices = self.list_devices()
        online = [d for d in devices if d.state == "device"]

        if online:
            device_id = self.select_device(devices)
            logger.info("Emulator already running: %s", device_id)
            self._status(f"Emulator already running: {device_id}", "info")
            if not self.is_device_booted(device_id):
                self.wait_for_device(device_id)
            return device_id

        avd_name = self._config.avd_name
        if not avd_name:
            available_avds = self.list_avds()
            if available_avds:
                avd_name = available_avds[0]
                logger.info("No avd_name configured, auto-detected AVD: %s", avd_name)
                self._status(f"Auto-detected AVD: {avd_name}", "info")
            else:
                raise DeviceNotFoundError(
                    "No emulator is running and no AVD is configured or detected. "
                    "Start an emulator manually or set avd_name in config."
                )

        emulator = self.resolve_emulator_path()
        cmd = [emulator, "-avd", avd_name]
        logger.info("Starting emulator: %s", " ".join(cmd))
        self._status(f"Starting emulator AVD '{avd_name}'...", "info")

        try:
            self._emulator_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_CREATE_NO_WINDOW,
                close_fds=True,
            )
            self._we_started_emulator = True
        except OSError as e:
            raise EmulatorStartError(f"Failed to start emulator: {e}") from e

        device_id = self._wait_for_new_device(avd_name)
        self.wait_for_device(device_id)
        return device_id

    def _wait_for_new_device(self, avd_name: str) -> str:
        deadline = time.time() + self._config.startup_timeout_seconds
        poll_interval = 3

        while time.time() < deadline:
            time.sleep(poll_interval)
            devices = self.list_devices()
            online = [d for d in devices if d.state == "device"]
            if online:
                device_id = online[0].serial
                logger.info("New emulator appeared: %s", device_id)
                return device_id

        raise EmulatorBootTimeoutError(
            f"Emulator for AVD '{avd_name}' did not appear within "
            f"{self._config.startup_timeout_seconds}s."
        )

    # ------------------------------------------------------------------
    # Package management
    # ------------------------------------------------------------------

    def is_package_installed(self, device_id: str, package: str) -> bool:
        adb = self.resolve_adb_path()
        result = self._run_adb(
            [adb, "-s", device_id, "shell", "pm", "list", "packages", package]
        )
        expected = f"package:{package}"
        return expected in result.stdout

    def launch_package(self, device_id: str, package: str) -> bool:
        adb = self.resolve_adb_path()
        cmd = [
            adb, "-s", device_id, "shell", "monkey",
            "-p", package, "-c", "android.intent.category.LAUNCHER", "1",
        ]
        logger.info("Launching package: %s", " ".join(cmd))
        result = self._run_adb(cmd)
        if result.returncode != 0:
            raise PackageLaunchError(
                f"monkey command failed for {package}: {result.stderr.strip()}"
            )
        if "No activities found" in result.stdout:
            raise PackageLaunchError(
                f"No launchable activity found for {package}."
            )
        return True

    # ------------------------------------------------------------------
    # Platform launch
    # ------------------------------------------------------------------

    def launch_platform(self, device_id: str, platform: MobilePlatform) -> PlatformLaunchResult:
        package = self._config.platform_packages.get(platform)
        if not package:
            return PlatformLaunchResult(
                platform=platform, success=False,
                message=f"No package name configured for {platform.display_name}.",
            )

        self._status(f"Checking {platform.display_name} ({package})...", "info")

        try:
            if not self.is_package_installed(device_id, package):
                msg = (
                    f"{platform.display_name} is not installed on the emulator "
                    f"or has a different package name: {package}"
                )
                logger.warning(msg)
                return PlatformLaunchResult(platform=platform, success=False, message=msg)
        except Exception as e:
            logger.exception("Install check failed for %s", platform.display_name)
            return PlatformLaunchResult(
                platform=platform, success=False,
                message=f"Install check failed: {e}",
            )

        self._status(f"Opening {platform.display_name}...", "info")
        try:
            self.launch_package(device_id, package)
            msg = f"{platform.display_name} opened successfully."
            logger.info(msg)
            self._status(msg, "success")
        except PackageLaunchError as e:
            logger.error("Failed to launch %s: %s", platform.display_name, e)
            return PlatformLaunchResult(platform=platform, success=False, message=str(e))
        except Exception as e:
            logger.exception("Unexpected error launching %s", platform.display_name)
            return PlatformLaunchResult(
                platform=platform, success=False,
                message=f"Unexpected launch error: {e}",
            )

        try:
            self._status(f"Waiting for {platform.display_name} to load...", "info")
            time.sleep(4)
            self._dismiss_popups(device_id, platform)
        except Exception as e:
            logger.exception("Non-critical error during popup dismissal for %s", platform.display_name)
            self._status(
                f"{platform.display_name}: popup dismissal skipped ({e})", "warning"
            )

        done_msg = f"Flow complete for {platform.display_name}."
        logger.info(done_msg)
        self._status(done_msg, "success")
        return PlatformLaunchResult(platform=platform, success=True, message=done_msg)

    def _dismiss_popups(self, device_id: str, platform: MobilePlatform):
        """Try to dismiss cookie/consent popups after app launch via ADB UI interaction.

        Completely non-critical -- any error here is swallowed and logged, never raised.
        """
        try:
            adb = self.resolve_adb_path()
        except Exception:
            return

        accept_texts = [
            "Accept All", "Accept all", "ACCEPT ALL",
            "Allow", "ALLOW", "Allow All",
            "I agree", "I AGREE", "Agree",
            "OK", "Ok", "GOT IT", "Got it",
            "Continue", "CONTINUE",
            "Not now", "Not Now", "NOT NOW",
        ]

        ui_xml = ""
        try:
            dump_cmd = [adb, "-s", device_id, "exec-out", "uiautomator", "dump", "/dev/tty"]
            result = self._run_adb(dump_cmd, timeout=8)
            ui_xml = result.stdout or ""
        except Exception as e:
            logger.debug("uiautomator dump skipped for %s: %s", platform.display_name, e)
            return

        for text in accept_texts:
            try:
                marker = f'text="{text}"'
                if marker not in ui_xml:
                    continue
                bounds = self._extract_bounds_for_text(ui_xml, text)
                if not bounds:
                    continue
                x, y = self._center_of_bounds(bounds)
                if x < 0 or y < 0:
                    continue
                tap_cmd = [adb, "-s", device_id, "shell", "input", "tap", str(x), str(y)]
                self._run_adb(tap_cmd, timeout=5)
                logger.info("Dismissed popup '%s' on %s at (%d, %d)", text, platform.display_name, x, y)
                self._status(f"Dismissed '{text}' popup on {platform.display_name}", "info")
                time.sleep(2)
                return
            except Exception as e:
                logger.debug("Popup action '%s' failed on %s: %s", text, platform.display_name, e)
                continue

    @staticmethod
    def _extract_bounds_for_text(ui_xml: str, text: str) -> Optional[str]:
        try:
            import re
            pattern = rf'text="{re.escape(text)}"[^>]*bounds="(\[[^\]]+\]\[[^\]]+\])"'
            match = re.search(pattern, ui_xml)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    @staticmethod
    def _center_of_bounds(bounds: str) -> tuple[int, int]:
        try:
            import re
            nums = [int(n) for n in re.findall(r'\d+', bounds)]
            if len(nums) < 4:
                return -1, -1
            x = (nums[0] + nums[2]) // 2
            y = (nums[1] + nums[3]) // 2
            return x, y
        except Exception:
            return -1, -1

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def prepare_device(self) -> str:
        """Resolve adb, ensure an emulator is running, return the device_id to use."""
        self._status("Resolving adb path...", "info")
        self.resolve_adb_path()
        self._status(f"adb found: {self._adb}", "success")

        self._status("Checking emulator status...", "info")
        device_id = self.start_emulator_if_needed()
        self._status(f"Using device: {device_id}", "success")
        return device_id

    def push_content_to_gallery(self, device_id: str, local_path: str) -> str:
        """Push a local file to /sdcard/DCIM/ContentUploader/ and refresh the media index.

        Returns the remote path on the device.
        Raises EmulatorError subclass on failure so the caller can show the pause dialog.
        """
        if not local_path or not os.path.isfile(local_path):
            raise PackageLaunchError(f"Local file does not exist: {local_path}")

        adb = self.resolve_adb_path()
        filename = os.path.basename(local_path)
        remote_dir = "/sdcard/DCIM/ContentUploader"
        remote_path = f"{remote_dir}/{filename}"

        self._status(f"Preparing remote directory {remote_dir}...", "info")
        logger.info("mkdir on device: %s", remote_dir)
        mkdir = self._run_adb(
            [adb, "-s", device_id, "shell", "mkdir", "-p", remote_dir],
            timeout=10,
        )
        if mkdir.returncode != 0:
            raise PackageLaunchError(
                f"Failed to create {remote_dir} on device: {mkdir.stderr.strip() or mkdir.stdout.strip()}"
            )

        self._status(f"Pushing '{filename}' to emulator gallery...", "info")
        logger.info("adb push %s -> %s", local_path, remote_path)
        push = self._run_adb(
            [adb, "-s", device_id, "push", local_path, remote_path],
            timeout=120,
        )
        if push.returncode != 0:
            raise PackageLaunchError(
                f"adb push failed: {push.stderr.strip() or push.stdout.strip()}"
            )

        self._status(f"Refreshing media scanner for {filename}...", "info")
        logger.info("Broadcasting MEDIA_SCANNER_SCAN_FILE for %s", remote_path)
        self._run_adb(
            [
                adb, "-s", device_id, "shell", "am", "broadcast",
                "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d", f"file://{remote_path}",
            ],
            timeout=15,
        )

        self._status(f"{filename} pushed into gallery.", "success")
        logger.info("Content push complete: %s", remote_path)
        return remote_path

    # ------------------------------------------------------------------
    # Profile picture / bio (per-platform UI tap sequences)
    # ------------------------------------------------------------------

    def set_profile_picture_in_app(
        self,
        device_id: str,
        platform: MobilePlatform,
        image_filename: str,
    ) -> None:
        """Navigate the platform's app to its 'change profile picture' UI and select the
        given file from the gallery. Best-effort: any failed step raises
        PackageLaunchError so the caller (worker) can pause for manual takeover.

        Sequences are based on common Android UI text in EN locale; if the locale
        differs they will fail and the caller will pause.
        """
        sequences = {
            MobilePlatform.INSTAGRAM: [
                ("Profile",),
                ("Edit profile",),
                ("Edit picture or avatar", "Change profile photo"),
                ("Choose from library", "New profile photo"),
            ],
            MobilePlatform.TIKTOK: [
                ("Profile",),
                ("Edit profile",),
                ("Profile photo", "Change photo"),
                ("Choose from gallery", "Select from gallery"),
            ],
            MobilePlatform.FACEBOOK: [
                ("Menu", "Your profile"),
                ("View profile",),
                ("Edit", "Edit profile"),
                ("Edit profile picture", "Update profile picture"),
                ("Select profile picture", "Choose profile picture"),
            ],
            MobilePlatform.YOUTUBE: [
                ("Your profile picture",),
                ("Manage your Google Account",),
                ("Personal info",),
                ("Photo",),
                ("Change",),
            ],
        }

        steps = sequences.get(platform)
        if not steps:
            raise PackageLaunchError(
                f"No PP navigation defined for {platform.display_name}"
            )

        self._status(f"Setting profile picture in {platform.display_name}...", "info")
        for step_alternatives in steps:
            self._tap_first_match(device_id, list(step_alternatives), platform.display_name)
            time.sleep(2.0)

        self._open_image_from_gallery(device_id, image_filename, platform.display_name)

        for confirm_text in ("Done", "Save", "Submit", "Apply", "Confirm", "Set as profile photo"):
            try:
                self._tap_first_match(device_id, [confirm_text], platform.display_name, soft=True)
                time.sleep(1.5)
            except Exception:
                continue

        self._status(f"{platform.display_name} profile picture step complete.", "success")
        logger.info("set_profile_picture_in_app done for %s", platform.display_name)

    def set_bio_in_app(
        self,
        device_id: str,
        platform: MobilePlatform,
        bio_text: str,
    ) -> None:
        """Navigate the platform's app to its 'edit bio' UI and overwrite the bio text.

        Supported: Instagram, TikTok, YouTube (channel description). Facebook profiles
        do not expose an in-app bio.
        """
        if platform not in (
            MobilePlatform.INSTAGRAM,
            MobilePlatform.TIKTOK,
            MobilePlatform.YOUTUBE,
        ):
            logger.info("Bio not supported on %s; skipping", platform.display_name)
            return

        if not bio_text.strip():
            return

        sequences = {
            MobilePlatform.INSTAGRAM: [("Profile",), ("Edit profile",), ("Bio",)],
            MobilePlatform.TIKTOK: [("Profile",), ("Edit profile",), ("Bio",)],
            MobilePlatform.YOUTUBE: [
                ("You", "Account"),
                ("Your channel", "View channel"),
                ("Edit channel", "Customize channel"),
                ("Description",),
            ],
        }
        steps = sequences[platform]

        self._status(f"Setting bio in {platform.display_name}...", "info")
        for step_alternatives in steps:
            self._tap_first_match(device_id, list(step_alternatives), platform.display_name)
            time.sleep(1.5)

        self._clear_text_field(device_id)
        self._input_text(device_id, bio_text)
        time.sleep(1.0)

        for confirm_text in ("Done", "Save", "Submit", "Apply"):
            try:
                self._tap_first_match(device_id, [confirm_text], platform.display_name, soft=True)
                time.sleep(1.5)
                break
            except Exception:
                continue

        try:
            self._press_back(device_id)
            time.sleep(0.8)
            for confirm_text in ("Save", "Done"):
                try:
                    self._tap_first_match(device_id, [confirm_text], platform.display_name, soft=True)
                    time.sleep(1.0)
                    break
                except Exception:
                    continue
        except Exception:
            pass

        self._status(f"{platform.display_name} bio step complete.", "success")
        logger.info("set_bio_in_app done for %s", platform.display_name)

    # ------------------------------------------------------------------
    # UI automation helpers
    # ------------------------------------------------------------------

    def _tap_first_match(
        self,
        device_id: str,
        candidates: list[str],
        platform_display: str,
        soft: bool = False,
    ) -> None:
        """Dump UI XML and tap the first node whose text or content-desc matches one of
        the candidates. If `soft` is True, returns silently when nothing matches."""
        adb = self.resolve_adb_path()
        try:
            dump = self._run_adb(
                [adb, "-s", device_id, "exec-out", "uiautomator", "dump", "/dev/tty"],
                timeout=8,
            )
            ui_xml = dump.stdout or ""
        except Exception as e:
            if soft:
                logger.debug("uiautomator dump failed (soft): %s", e)
                return
            raise PackageLaunchError(f"uiautomator dump failed: {e}") from e

        for cand in candidates:
            bounds = self._extract_bounds_for_attr(ui_xml, "text", cand)
            if not bounds:
                bounds = self._extract_bounds_for_attr(ui_xml, "content-desc", cand)
            if not bounds:
                continue
            x, y = self._center_of_bounds(bounds)
            if x < 0 or y < 0:
                continue
            try:
                self._run_adb(
                    [adb, "-s", device_id, "shell", "input", "tap", str(x), str(y)],
                    timeout=5,
                )
                logger.info("Tapped '%s' on %s at (%d, %d)", cand, platform_display, x, y)
                return
            except Exception as e:
                logger.warning("Tap '%s' failed on %s: %s", cand, platform_display, e)
                continue

        if soft:
            return
        raise PackageLaunchError(
            f"Could not find UI element on {platform_display}: tried {candidates}"
        )

    def _open_image_from_gallery(
        self,
        device_id: str,
        image_filename: str,
        platform_display: str,
    ) -> None:
        """After hitting 'Choose from library' / 'Select from gallery', tap the
        Google Photos source if visible and then the first image from our pushed folder.
        """
        try:
            self._tap_first_match(device_id, ["Google Photos"], platform_display, soft=True)
            time.sleep(1.5)
        except Exception:
            pass

        try:
            self._tap_first_match(device_id, ["ContentUploader"], platform_display, soft=True)
            time.sleep(1.5)
        except Exception:
            pass

        try:
            self._tap_first_match(
                device_id, [image_filename], platform_display, soft=True,
            )
            time.sleep(1.5)
            return
        except Exception:
            pass

        adb = self.resolve_adb_path()
        try:
            dump = self._run_adb(
                [adb, "-s", device_id, "exec-out", "uiautomator", "dump", "/dev/tty"],
                timeout=8,
            )
            ui_xml = dump.stdout or ""
        except Exception as e:
            raise PackageLaunchError(f"Could not dump UI to find image: {e}") from e

        import re
        match = re.search(r'class="android\.widget\.ImageView"[^>]*bounds="(\[[^\]]+\]\[[^\]]+\])"', ui_xml)
        if not match:
            raise PackageLaunchError(
                f"Could not find any image in gallery on {platform_display}"
            )
        bounds = match.group(1)
        x, y = self._center_of_bounds(bounds)
        if x < 0:
            raise PackageLaunchError("Bad bounds while picking gallery image")
        self._run_adb(
            [adb, "-s", device_id, "shell", "input", "tap", str(x), str(y)],
            timeout=5,
        )
        logger.info("Tapped first ImageView in gallery on %s at (%d, %d)", platform_display, x, y)
        time.sleep(1.5)

    def _input_text(self, device_id: str, text: str) -> None:
        """adb shell input text -- escapes spaces and special chars."""
        adb = self.resolve_adb_path()
        escaped = (
            text.replace("\\", "\\\\")
                .replace(" ", "%s")
                .replace("'", "\\'")
                .replace('"', '\\"')
                .replace("&", "\\&")
                .replace("<", "\\<")
                .replace(">", "\\>")
                .replace("|", "\\|")
                .replace(";", "\\;")
                .replace("(", "\\(")
                .replace(")", "\\)")
        )
        self._run_adb(
            [adb, "-s", device_id, "shell", "input", "text", escaped],
            timeout=10,
        )

    def _clear_text_field(self, device_id: str) -> None:
        """Select all + delete to clear the current text input."""
        adb = self.resolve_adb_path()
        try:
            self._run_adb(
                [adb, "-s", device_id, "shell", "input", "keyevent", "KEYCODE_MOVE_END"],
                timeout=5,
            )
            for _ in range(120):
                self._run_adb(
                    [adb, "-s", device_id, "shell", "input", "keyevent", "KEYCODE_DEL"],
                    timeout=3,
                )
        except Exception as e:
            logger.warning("Failed to fully clear text field: %s", e)

    def _press_back(self, device_id: str) -> None:
        adb = self.resolve_adb_path()
        self._run_adb(
            [adb, "-s", device_id, "shell", "input", "keyevent", "KEYCODE_BACK"],
            timeout=5,
        )

    @staticmethod
    def _extract_bounds_for_attr(ui_xml: str, attr: str, value: str) -> Optional[str]:
        try:
            import re
            pattern = rf'{attr}="{re.escape(value)}"[^>]*bounds="(\[[^\]]+\]\[[^\]]+\])"'
            match = re.search(pattern, ui_xml)
            if match:
                return match.group(1)
            pattern2 = rf'bounds="(\[[^\]]+\]\[[^\]]+\])"[^>]*{attr}="{re.escape(value)}"'
            match2 = re.search(pattern2, ui_xml)
            if match2:
                return match2.group(1)
        except Exception:
            pass
        return None

    def shutdown_emulator(self, device_id: Optional[str] = None) -> None:
        """Shut down the emulator that WE started. Leaves pre-existing emulators alone.

        Uses `adb emu kill` to cleanly stop the emulator (which also closes the
        associated qemu console). Falls back to terminating the Popen process.
        """
        if not self._we_started_emulator:
            logger.info("Shutdown skipped: emulator was already running before we started.")
            self._status("Leaving existing emulator running.", "info")
            return

        self._status("Shutting down emulator...", "info")
        logger.info("Requesting emulator shutdown")

        try:
            if device_id:
                adb = self.resolve_adb_path()
                self._run_adb([adb, "-s", device_id, "emu", "kill"], timeout=5)
                logger.info("adb emu kill sent to %s", device_id)
        except Exception as e:
            logger.warning("adb emu kill failed: %s", e)

        try:
            if self._emulator_proc:
                for _ in range(20):
                    if self._emulator_proc.poll() is not None:
                        break
                    time.sleep(0.5)
                if self._emulator_proc.poll() is None:
                    logger.warning("Emulator did not exit via adb emu kill; terminating process")
                    self._emulator_proc.terminate()
                    try:
                        self._emulator_proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning("Emulator process still alive; killing")
                        self._emulator_proc.kill()
        except Exception as e:
            logger.warning("Failed to terminate emulator process: %s", e)
        finally:
            self._emulator_proc = None
            self._we_started_emulator = False
            logger.info("Emulator shutdown complete")
            self._status("Emulator closed.", "success")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_adb(
        self,
        cmd: list[str],
        timeout: Optional[int] = None,
    ) -> subprocess.CompletedProcess:
        timeout = timeout or self._config.command_timeout_seconds
        logger.debug("Running: %s", " ".join(cmd))
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=_CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as e:
            logger.error("Command timed out (%ds): %s", timeout, " ".join(cmd))
            raise
        except FileNotFoundError as e:
            logger.error("Command not found: %s", cmd[0])
            raise AdbNotFoundError(f"Could not execute: {cmd[0]}") from e
