from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    # Backgrounds
    bg_app = "#060606"
    bg_shell = "#0B0B0C"
    bg_panel = "#101112"
    bg_card = "#151617"
    bg_card_hover = "#1B1D1F"
    bg_card_active = "#202326"
    bg_input = "#121314"
    bg_popup = "#17191B"

    # Borders
    border_soft = "#232629"
    border_default = "#2C3034"
    border_strong = "#3A3F45"

    # Text
    text_primary = "#F2F2F2"
    text_secondary = "#C9CDD2"
    text_muted = "#8A9097"
    text_disabled = "#62686F"

    # Status - Success
    success = "#4E7F5F"
    success_text = "#8FC7A1"
    success_bg = "#162019"

    # Status - Warning
    warning = "#9A6B36"
    warning_text = "#D8A46B"
    warning_bg = "#211A14"

    # Status - Danger
    danger = "#8B4A4A"
    danger_text = "#D68E8E"
    danger_bg = "#211616"

    # Status - Neutral
    neutral_state = "#5E666F"
    neutral_state_text = "#A9B0B7"
    neutral_state_bg = "#181A1C"

    # Primary button (cyan accent)
    primary_bg = "#1E2A2E"
    primary_text = "#5ECFDF"
    primary_hover = "#253538"
    primary_pressed = "#1A2428"
    primary_border = "#3A8A96"

    # Confirm button (green accent)
    confirm_bg = "#1A2B1F"
    confirm_text = "#5ED88B"
    confirm_hover = "#213A28"
    confirm_pressed = "#162418"
    confirm_border = "#3A8A56"

    # Danger button (red accent)
    danger_btn_bg = "#2B1A1A"
    danger_btn_text = "#E06060"
    danger_btn_hover = "#3A2121"
    danger_btn_pressed = "#241616"
    danger_btn_border = "#8A3A3A"

    # Sidebar active indicator
    sidebar_indicator = "#5B6168"


COLORS = Colors()

APP_NAME = "ContentUploader"
APP_DATA_DIR_NAME = ".content-uploader"

PLATFORMS = {
    "tiktok": {
        "id": "tiktok",
        "display_name": "TikTok",
        "login_url": "https://www.tiktok.com/login/phone-or-email/email",
        "base_url": "https://www.tiktok.com",
    },
    "instagram": {
        "id": "instagram",
        "display_name": "Instagram",
        "login_url": "https://www.instagram.com/accounts/login/",
        "base_url": "https://www.instagram.com",
    },
    "facebook": {
        "id": "facebook",
        "display_name": "Facebook",
        "login_url": "https://www.facebook.com/login",
        "base_url": "https://www.facebook.com",
    },
    "youtube": {
        "id": "youtube",
        "display_name": "YouTube",
        "login_url": "https://accounts.google.com/",
        "base_url": "https://studio.youtube.com",
    },
}

# ---------------------------------------------------------------------------
# Android Emulator defaults
# TODO: Add settings page for adb_path, emulator_path, avd_name, device_id, package_names
# ---------------------------------------------------------------------------
DEFAULT_EMULATOR_CONFIG = {
    "adb_path": None,
    "emulator_path": None,
    "avd_name": "Content",
    "device_id": None,
    "startup_timeout_seconds": 90,
    "command_timeout_seconds": 20,
    "platform_packages": {
        "tiktok": "com.zhiliaoapp.musically",
        "facebook": "com.facebook.katana",
        "instagram": "com.instagram.android",
        "youtube": "com.google.android.youtube",
    },
}

CONTENT_TYPES = {
    "tiktok": [
        {
            "type": "video",
            "label": "Video",
            "formats": [".mp4", ".mov", ".webm"],
            "max_size_mb": 4096,
            "min_duration": 3,
            "max_duration": 600,
            "aspect_ratios": ["9:16"],
            "caption_max": 2200,
            "media": "video",
        },
        {
            "type": "photo",
            "label": "Photo",
            "formats": [".jpeg", ".jpg", ".webp"],
            "max_size_mb": 20,
            "caption_max": 4000,
            "media": "image",
        },
        {
            "type": "carousel",
            "label": "Carousel",
            "formats": [".jpeg", ".jpg", ".webp"],
            "max_size_mb": 20,
            "min_items": 2,
            "max_items": 35,
            "caption_max": 4000,
            "media": "image",
        },
    ],
    "instagram": [
        {
            "type": "photo",
            "label": "Photo Post",
            "formats": [".jpeg", ".jpg", ".png"],
            "max_size_mb": 8,
            "aspect_ratios": ["1:1", "4:5", "1.91:1"],
            "caption_max": 2200,
            "media": "image",
        },
        {
            "type": "reel",
            "label": "Reel",
            "formats": [".mp4", ".mov"],
            "max_size_mb": 100,
            "min_duration": 5,
            "max_duration": 90,
            "aspect_ratios": ["9:16"],
            "caption_max": 2200,
            "media": "video",
        },
        {
            "type": "story",
            "label": "Story",
            "formats": [".jpeg", ".jpg", ".png", ".mp4", ".mov"],
            "max_size_mb": 100,
            "max_duration": 60,
            "aspect_ratios": ["9:16"],
            "caption_max": 2200,
            "media": "both",
        },
        {
            "type": "carousel",
            "label": "Carousel",
            "formats": [".jpeg", ".jpg", ".png", ".mp4", ".mov"],
            "max_size_mb": 100,
            "max_duration": 60,
            "min_items": 2,
            "max_items": 10,
            "caption_max": 2200,
            "media": "both",
        },
    ],
    "facebook": [
        {
            "type": "photo",
            "label": "Photo Post",
            "formats": [".jpeg", ".jpg", ".png", ".bmp", ".gif", ".tiff"],
            "max_size_mb": 10,
            "media": "image",
        },
        {
            "type": "video",
            "label": "Video Post",
            "formats": [".mp4", ".mov"],
            "max_size_mb": 10240,
            "max_duration": 14400,
            "media": "video",
        },
        {
            "type": "reel",
            "label": "Reel",
            "formats": [".mp4"],
            "max_size_mb": 4096,
            "min_duration": 3,
            "max_duration": 90,
            "aspect_ratios": ["9:16"],
            "media": "video",
        },
        {
            "type": "story",
            "label": "Story",
            "formats": [".jpeg", ".jpg", ".png", ".mp4", ".mov"],
            "max_size_mb": 100,
            "max_duration": 60,
            "aspect_ratios": ["9:16"],
            "media": "both",
        },
        {
            "type": "carousel",
            "label": "Carousel",
            "formats": [".jpeg", ".jpg", ".png"],
            "max_size_mb": 10,
            "min_items": 2,
            "max_items": 10,
            "media": "image",
        },
    ],
    "youtube": [
        {
            "type": "video",
            "label": "Video",
            "formats": [".mp4", ".mov", ".avi", ".wmv", ".flv", ".webm", ".mkv"],
            "max_size_mb": 262144,
            "max_duration": 43200,
            "aspect_ratios": ["16:9"],
            "media": "video",
            "extra_fields": ["tags", "category"],
        },
        {
            "type": "short",
            "label": "Short",
            "formats": [".mp4", ".mov", ".webm"],
            "max_size_mb": 262144,
            "max_duration": 180,
            "aspect_ratios": ["9:16", "1:1"],
            "media": "video",
        },
    ],
}
