import time

from flask import current_app
from sqlalchemy import text

from app import db

_CACHE: dict[str, tuple[str, float]] = {}
_TTL_SECONDS = 600
OTP_SETTING_TTL_SECONDS = 0

def get_setting(key: str, default: str = "", ttl: int = _TTL_SECONDS) -> str:
    if not key:
        return default

    hit = _CACHE.get(key)
    if hit and (time.monotonic() - hit[1]) < ttl:
        return hit[0]

    try:
        row = db.session.execute(
            text("SELECT TOP 1 [Value] FROM SettingsEmail WITH (NOLOCK) WHERE [Key] = :k"),
            {"k": key},
        ).first()
        value = (row[0] or "").strip() if row else ""
    except Exception:
        current_app.logger.exception("SettingsEmail lookup failed for key=%r", key)
        return default

    if not value:
        return default

    _CACHE[key] = (value, time.monotonic())
    return value

def clear_settings_cache(key: str | None = None) -> None:
    if key is None:
        _CACHE.clear()
    else:
        _CACHE.pop(key, None)

def otp_required() -> bool:
    return get_setting("otp_genius", "0", ttl=OTP_SETTING_TTL_SECONDS).strip() == "0"

def company_name() -> str:
    return get_setting(
        "graph_sender_name",
        current_app.config.get("COMPANY_NAME", ""),
    )