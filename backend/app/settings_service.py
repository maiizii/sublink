"""Helpers for reading and mutating site-wide settings."""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    DEFAULT_ICON_URL,
    DEFAULT_LOGO_URL,
    DEFAULT_SHORT_CODE_LENGTH,
    DEFAULT_SHORT_LINK_PATH,
    DEFAULT_SITE_DOMAIN,
    SessionLocal,
    SiteSettings,
)

_MIN_SHORT_CODE_LENGTH = 3
_MAX_SHORT_CODE_LENGTH = 64


def normalize_site_domain(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return DEFAULT_SITE_DOMAIN
    if raw.startswith("http://") or raw.startswith("https://"):
        raw = raw.split("://", 1)[1]
    raw = raw.split("/", 1)[0]
    return raw or DEFAULT_SITE_DOMAIN


def normalize_short_link_path(value: str | None) -> str:
    """Normalize the configured short link path to a canonical form."""

    raw = (value or "").strip()
    if not raw or raw == "/":
        return "/"

    if raw.startswith("http://") or raw.startswith("https://"):
        raw = raw.split("://", 1)[1]
        raw = raw.split("/", 1)[1] if "/" in raw else ""

    segments = [segment.strip() for segment in raw.strip("/").split("/") if segment.strip()]
    if not segments:
        return "/"
    normalized = "/" + "/".join(segments) + "/"
    return normalized


def normalize_short_code_length(value: int | None) -> int:
    length = value or DEFAULT_SHORT_CODE_LENGTH
    if length < _MIN_SHORT_CODE_LENGTH:
        return _MIN_SHORT_CODE_LENGTH
    if length > _MAX_SHORT_CODE_LENGTH:
        return _MAX_SHORT_CODE_LENGTH
    return length


def normalize_asset_url(value: str | None, fallback: str) -> str:
    raw = (value or "").strip()
    return raw or fallback


def _default_settings_payload() -> dict[str, Any]:
    env_domain = os.getenv("BASE_DOMAIN")
    env_short_len = os.getenv("SHORT_CODE_LEN")
    env_short_path = os.getenv("SHORT_LINK_PATH")
    env_logo = os.getenv("SITE_LOGO_URL")
    env_icon = os.getenv("SITE_ICON_URL")

    length = DEFAULT_SHORT_CODE_LENGTH
    if env_short_len:
        try:
            length = int(env_short_len)
        except ValueError:
            length = DEFAULT_SHORT_CODE_LENGTH

    payload = {
        "site_domain": normalize_site_domain(env_domain),
        "short_code_length": normalize_short_code_length(length),
        "short_link_path": normalize_short_link_path(env_short_path or DEFAULT_SHORT_LINK_PATH),
        "logo_url": normalize_asset_url(env_logo, DEFAULT_LOGO_URL),
        "icon_url": normalize_asset_url(env_icon, DEFAULT_ICON_URL),
    }
    return payload


def ensure_default_settings() -> None:
    """Ensure a settings row exists with sane defaults."""

    with SessionLocal() as session:
        existing = session.scalar(select(SiteSettings).order_by(SiteSettings.id).limit(1))
        if existing is not None:
            return
        payload = _default_settings_payload()
        settings = SiteSettings(**payload)
        session.add(settings)
        session.commit()


def get_site_settings(db: Session) -> SiteSettings:
    """Fetch the single settings row, creating one with defaults if necessary."""

    settings = db.scalar(select(SiteSettings).order_by(SiteSettings.id).limit(1))
    if settings is not None:
        return settings

    payload = _default_settings_payload()
    settings = SiteSettings(**payload)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def update_site_settings(
    db: Session,
    *,
    site_domain: str,
    short_code_length: int,
    short_link_path: str,
    logo_url: str,
    icon_url: str,
) -> SiteSettings:
    """Persist new settings values and return the updated row."""

    settings = get_site_settings(db)
    settings.site_domain = normalize_site_domain(site_domain)
    settings.short_code_length = normalize_short_code_length(short_code_length)
    settings.short_link_path = normalize_short_link_path(short_link_path)
    settings.logo_url = normalize_asset_url(logo_url, DEFAULT_LOGO_URL)
    settings.icon_url = normalize_asset_url(icon_url, DEFAULT_ICON_URL)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def build_short_link_prefix(settings: SiteSettings) -> str:
    """Compose the short link prefix shown in the UI."""

    domain = settings.site_domain.strip().strip("/") or DEFAULT_SITE_DOMAIN
    base_url = f"https://{domain}".rstrip("/")
    path = settings.short_link_path
    if not path.startswith("/"):
        path = f"/{path}"
    if path != "/" and not path.endswith("/"):
        path = f"{path}/"
    return f"{base_url}{path}"


def extract_short_code(path: str, settings: SiteSettings) -> str | None:
    """Extract a short code from the request path based on configured prefix."""

    configured = settings.short_link_path
    if configured != "/":
        trimmed_path = path.strip("/")
        normalized_prefix = "/".join(
            segment for segment in configured.strip("/").split("/") if segment
        )
        if not normalized_prefix:
            normalized_prefix = ""
        if not trimmed_path.startswith(normalized_prefix):
            return None
        remainder = trimmed_path[len(normalized_prefix) :]
        if remainder.startswith("/"):
            remainder = remainder[1:]
        elif remainder:
            return None
    else:
        remainder = path.strip("/")

    if not remainder or "/" in remainder:
        return None
    return remainder
