import os

from app.constants import CONTENT_TYPES
from app.db.models import Content


def get_compatible_targets(content: Content) -> list[tuple[str, dict]]:
    """Return list of (platform_id, content_type_dict) that match this content's specs."""
    results = []
    ext = os.path.splitext(content.file_name)[1].lower() if content.file_name else ""
    is_video = content.mime_type.startswith("video/")
    is_image = content.mime_type.startswith("image/")
    size_mb = content.file_size / (1024 * 1024) if content.file_size else 0

    for platform_id, types in CONTENT_TYPES.items():
        for ct in types:
            if not _format_matches(ext, ct.get("formats", [])):
                continue

            if ct.get("media") == "video" and not is_video:
                continue
            if ct.get("media") == "image" and not is_image:
                continue

            if ct.get("max_size_mb") and size_mb > ct["max_size_mb"]:
                continue

            if is_video and content.duration_seconds > 0:
                if ct.get("min_duration") and content.duration_seconds < ct["min_duration"]:
                    continue
                if ct.get("max_duration") and content.duration_seconds > ct["max_duration"]:
                    continue

            if ct.get("min_items"):
                continue

            results.append((platform_id, ct))

    return results


def _format_matches(ext: str, formats: list[str]) -> bool:
    if not formats:
        return True
    return ext in formats
