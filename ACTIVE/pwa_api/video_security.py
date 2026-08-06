"""Small, dependency-free helpers for protected lesson video delivery."""

from __future__ import annotations

import hashlib
import hmac
import re
from pathlib import Path
from typing import Optional, Tuple


VIDEO_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,95}$")


def validate_video_id(video_id: str) -> str:
    if not VIDEO_ID_RE.fullmatch(video_id or ""):
        raise ValueError("invalid video id")
    return video_id


def video_file_path(storage_dir: Path, video_id: str) -> Path:
    """Map an opaque id to one MP4 inside the configured private directory."""
    validate_video_id(video_id)
    root = storage_dir.resolve()
    candidate = (root / f"{video_id}.mp4").resolve()
    if candidate.parent != root:
        raise ValueError("video path escapes storage directory")
    return candidate


def video_signature(secret: str, video_id: str, user_id: int, expires_at: int) -> str:
    validate_video_id(video_id)
    if not secret:
        raise ValueError("video signing secret is not configured")
    payload = f"v1:{video_id}:{int(user_id)}:{int(expires_at)}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_video_signature(
    secret: str,
    video_id: str,
    user_id: int,
    expires_at: int,
    signature: str,
    now: int,
) -> bool:
    if expires_at < now or expires_at > now + 86_400 or not signature:
        return False
    try:
        expected = video_signature(secret, video_id, user_id, expires_at)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(expected, signature)


def parse_byte_range(value: Optional[str], file_size: int) -> Optional[Tuple[int, int]]:
    """Parse a single RFC 7233 byte range. Multiple ranges are intentionally rejected."""
    if not value:
        return None
    if file_size <= 0 or not value.startswith("bytes=") or "," in value:
        raise ValueError("invalid range")
    raw = value[6:].strip()
    if "-" not in raw:
        raise ValueError("invalid range")
    start_raw, end_raw = raw.split("-", 1)
    try:
        if not start_raw:
            suffix = int(end_raw)
            if suffix <= 0:
                raise ValueError("invalid suffix")
            start = max(0, file_size - suffix)
            end = file_size - 1
        else:
            start = int(start_raw)
            end = int(end_raw) if end_raw else file_size - 1
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid range") from exc
    if start < 0 or start >= file_size or end < start:
        raise ValueError("unsatisfiable range")
    return start, min(end, file_size - 1)
