from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


class MobilePlatform(enum.Enum):
    TIKTOK = "tiktok"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"

    @property
    def platform_id(self) -> str:
        return self.value

    @property
    def display_name(self) -> str:
        return {
            MobilePlatform.TIKTOK: "TikTok",
            MobilePlatform.FACEBOOK: "Facebook",
            MobilePlatform.INSTAGRAM: "Instagram",
            MobilePlatform.YOUTUBE: "YouTube",
        }[self]


DEFAULT_PLATFORM_PACKAGES: dict[MobilePlatform, str] = {
    MobilePlatform.TIKTOK: "com.zhiliaoapp.musically",
    MobilePlatform.FACEBOOK: "com.facebook.katana",
    MobilePlatform.INSTAGRAM: "com.instagram.android",
    MobilePlatform.YOUTUBE: "com.google.android.youtube",
}


@dataclass
class AndroidEmulatorConfig:
    adb_path: Optional[str] = None
    emulator_path: Optional[str] = None
    avd_name: Optional[str] = None
    device_id: Optional[str] = None
    startup_timeout_seconds: int = 90
    command_timeout_seconds: int = 20
    platform_packages: dict[MobilePlatform, str] = field(
        default_factory=lambda: dict(DEFAULT_PLATFORM_PACKAGES)
    )


@dataclass
class AndroidDeviceInfo:
    serial: str
    state: str  # "device", "offline", "unauthorized"


@dataclass
class PlatformLaunchResult:
    platform: MobilePlatform
    success: bool
    message: str


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class EmulatorError(Exception):
    """Base exception for all emulator-related errors."""


class AdbNotFoundError(EmulatorError):
    """adb.exe could not be located on this system."""


class EmulatorNotFoundError(EmulatorError):
    """emulator.exe could not be located on this system."""


class DeviceNotFoundError(EmulatorError):
    """No ADB device/emulator is connected."""


class DeviceSelectionError(EmulatorError):
    """Multiple devices found but no device_id configured."""


class EmulatorStartError(EmulatorError):
    """Failed to start the Android emulator process."""


class EmulatorBootTimeoutError(EmulatorError):
    """Emulator did not finish booting within the timeout."""


class PackageNotInstalledError(EmulatorError):
    """The requested package is not installed on the device."""


class PackageLaunchError(EmulatorError):
    """Failed to launch the requested package."""
