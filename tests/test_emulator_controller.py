"""Unit tests for AndroidEmulatorController -- parsing, device selection, command building."""

from unittest.mock import patch, MagicMock
import subprocess

import pytest

from app.mobile.emulator_config import (
    AndroidDeviceInfo,
    AndroidEmulatorConfig,
    AdbNotFoundError,
    DeviceNotFoundError,
    DeviceSelectionError,
    EmulatorNotFoundError,
    MobilePlatform,
    DEFAULT_PLATFORM_PACKAGES,
)
from app.mobile.emulator_controller import AndroidEmulatorController


# ---------------------------------------------------------------------------
# parse_devices_output
# ---------------------------------------------------------------------------

class TestParseDevicesOutput:
    def test_empty_output(self):
        output = "List of devices attached\n\n"
        result = AndroidEmulatorController.parse_devices_output(output)
        assert result == []

    def test_single_device(self):
        output = "List of devices attached\nemulator-5554\tdevice\n\n"
        result = AndroidEmulatorController.parse_devices_output(output)
        assert len(result) == 1
        assert result[0].serial == "emulator-5554"
        assert result[0].state == "device"

    def test_multiple_devices(self):
        output = (
            "List of devices attached\n"
            "emulator-5554\tdevice\n"
            "emulator-5556\tdevice\n"
            "192.168.1.100:5555\toffline\n"
            "\n"
        )
        result = AndroidEmulatorController.parse_devices_output(output)
        assert len(result) == 3
        assert result[0] == AndroidDeviceInfo(serial="emulator-5554", state="device")
        assert result[1] == AndroidDeviceInfo(serial="emulator-5556", state="device")
        assert result[2] == AndroidDeviceInfo(serial="192.168.1.100:5555", state="offline")

    def test_unauthorized_device(self):
        output = "List of devices attached\nemulator-5554\tunauthorized\n\n"
        result = AndroidEmulatorController.parse_devices_output(output)
        assert len(result) == 1
        assert result[0].state == "unauthorized"

    def test_only_header(self):
        output = "List of devices attached\n"
        result = AndroidEmulatorController.parse_devices_output(output)
        assert result == []


# ---------------------------------------------------------------------------
# select_device
# ---------------------------------------------------------------------------

class TestSelectDevice:
    def _controller(self, device_id=None):
        config = AndroidEmulatorConfig(device_id=device_id)
        return AndroidEmulatorController(config)

    def test_single_device_no_config(self):
        ctrl = self._controller()
        devices = [AndroidDeviceInfo(serial="emulator-5554", state="device")]
        assert ctrl.select_device(devices) == "emulator-5554"

    def test_multiple_devices_no_config_raises(self):
        ctrl = self._controller()
        devices = [
            AndroidDeviceInfo(serial="emulator-5554", state="device"),
            AndroidDeviceInfo(serial="emulator-5556", state="device"),
        ]
        with pytest.raises(DeviceSelectionError):
            ctrl.select_device(devices)

    def test_multiple_devices_with_config(self):
        ctrl = self._controller(device_id="emulator-5556")
        devices = [
            AndroidDeviceInfo(serial="emulator-5554", state="device"),
            AndroidDeviceInfo(serial="emulator-5556", state="device"),
        ]
        assert ctrl.select_device(devices) == "emulator-5556"

    def test_configured_device_not_found(self):
        ctrl = self._controller(device_id="emulator-9999")
        devices = [AndroidDeviceInfo(serial="emulator-5554", state="device")]
        with pytest.raises(DeviceNotFoundError):
            ctrl.select_device(devices)

    def test_configured_device_offline(self):
        ctrl = self._controller(device_id="emulator-5554")
        devices = [AndroidDeviceInfo(serial="emulator-5554", state="offline")]
        with pytest.raises(DeviceNotFoundError, match="offline"):
            ctrl.select_device(devices)

    def test_no_online_devices(self):
        ctrl = self._controller()
        devices = [AndroidDeviceInfo(serial="emulator-5554", state="offline")]
        with pytest.raises(DeviceNotFoundError):
            ctrl.select_device(devices)

    def test_empty_device_list(self):
        ctrl = self._controller()
        with pytest.raises(DeviceNotFoundError):
            ctrl.select_device([])


# ---------------------------------------------------------------------------
# Platform -> package mapping
# ---------------------------------------------------------------------------

class TestPlatformPackages:
    def test_default_packages(self):
        assert DEFAULT_PLATFORM_PACKAGES[MobilePlatform.TIKTOK] == "com.zhiliaoapp.musically"
        assert DEFAULT_PLATFORM_PACKAGES[MobilePlatform.FACEBOOK] == "com.facebook.katana"
        assert DEFAULT_PLATFORM_PACKAGES[MobilePlatform.INSTAGRAM] == "com.instagram.android"
        assert DEFAULT_PLATFORM_PACKAGES[MobilePlatform.YOUTUBE] == "com.google.android.youtube"

    def test_config_uses_defaults(self):
        config = AndroidEmulatorConfig()
        assert config.platform_packages[MobilePlatform.TIKTOK] == "com.zhiliaoapp.musically"

    def test_config_custom_package(self):
        custom = {MobilePlatform.TIKTOK: "com.ss.android.ugc.trill"}
        config = AndroidEmulatorConfig(platform_packages=custom)
        assert config.platform_packages[MobilePlatform.TIKTOK] == "com.ss.android.ugc.trill"
        assert MobilePlatform.INSTAGRAM not in config.platform_packages

    def test_mobile_platform_enum_values(self):
        assert MobilePlatform.TIKTOK.platform_id == "tiktok"
        assert MobilePlatform.FACEBOOK.platform_id == "facebook"
        assert MobilePlatform.INSTAGRAM.platform_id == "instagram"
        assert MobilePlatform.YOUTUBE.platform_id == "youtube"

    def test_mobile_platform_display_names(self):
        assert MobilePlatform.TIKTOK.display_name == "TikTok"
        assert MobilePlatform.FACEBOOK.display_name == "Facebook"
        assert MobilePlatform.INSTAGRAM.display_name == "Instagram"
        assert MobilePlatform.YOUTUBE.display_name == "YouTube"


# ---------------------------------------------------------------------------
# resolve_adb_path
# ---------------------------------------------------------------------------

class TestResolveAdbPath:
    def test_explicit_config_path(self, tmp_path):
        adb_file = tmp_path / "adb.exe"
        adb_file.write_text("")
        config = AndroidEmulatorConfig(adb_path=str(adb_file))
        ctrl = AndroidEmulatorController(config)
        assert ctrl.resolve_adb_path() == str(adb_file)

    @patch("shutil.which", return_value=None)
    @patch("os.path.isfile", return_value=False)
    def test_not_found_raises(self, mock_isfile, mock_which):
        config = AndroidEmulatorConfig()
        ctrl = AndroidEmulatorController(config)
        with pytest.raises(AdbNotFoundError):
            ctrl.resolve_adb_path()

    @patch("shutil.which", return_value=r"C:\Android\platform-tools\adb.exe")
    def test_found_on_path(self, mock_which):
        config = AndroidEmulatorConfig()
        ctrl = AndroidEmulatorController(config)
        assert ctrl.resolve_adb_path() == r"C:\Android\platform-tools\adb.exe"

    @patch("shutil.which", return_value=None)
    @patch("os.environ.get")
    @patch("os.path.isfile")
    def test_found_via_localappdata(self, mock_isfile, mock_env, mock_which):
        def env_side_effect(key, *args):
            if key == "LOCALAPPDATA":
                return r"C:\Users\test\AppData\Local"
            return None

        mock_env.side_effect = env_side_effect

        expected = r"C:\Users\test\AppData\Local\Android\Sdk\platform-tools\adb.exe"
        mock_isfile.side_effect = lambda p: p == expected

        config = AndroidEmulatorConfig()
        ctrl = AndroidEmulatorController(config)
        assert ctrl.resolve_adb_path() == expected


# ---------------------------------------------------------------------------
# resolve_emulator_path
# ---------------------------------------------------------------------------

class TestResolveEmulatorPath:
    def test_explicit_config_path(self, tmp_path):
        emu_file = tmp_path / "emulator.exe"
        emu_file.write_text("")
        config = AndroidEmulatorConfig(emulator_path=str(emu_file))
        ctrl = AndroidEmulatorController(config)
        assert ctrl.resolve_emulator_path() == str(emu_file)

    @patch("shutil.which", return_value=None)
    @patch("os.path.isfile", return_value=False)
    def test_not_found_raises(self, mock_isfile, mock_which):
        config = AndroidEmulatorConfig()
        ctrl = AndroidEmulatorController(config)
        with pytest.raises(EmulatorNotFoundError):
            ctrl.resolve_emulator_path()


# ---------------------------------------------------------------------------
# is_package_installed
# ---------------------------------------------------------------------------

class TestIsPackageInstalled:
    @patch.object(AndroidEmulatorController, "resolve_adb_path", return_value="adb")
    @patch("subprocess.run")
    def test_package_found(self, mock_run, mock_adb):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="package:com.instagram.android\n", stderr=""
        )
        config = AndroidEmulatorConfig()
        ctrl = AndroidEmulatorController(config)
        assert ctrl.is_package_installed("emulator-5554", "com.instagram.android") is True

    @patch.object(AndroidEmulatorController, "resolve_adb_path", return_value="adb")
    @patch("subprocess.run")
    def test_package_not_found(self, mock_run, mock_adb):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        config = AndroidEmulatorConfig()
        ctrl = AndroidEmulatorController(config)
        assert ctrl.is_package_installed("emulator-5554", "com.instagram.android") is False
