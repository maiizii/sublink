"""Helpers for reading and mutating site-wide settings."""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from .models import (
    DEFAULT_ICON_URL,
    DEFAULT_LOGO_URL,
    DEFAULT_SHORT_CODE_LENGTH,
    DEFAULT_SHORT_LINK_PATH,
    DEFAULT_SITE_DOMAIN,
    Base,
    SessionLocal,
    SiteSettings,
    engine,
)

_MIN_SHORT_CODE_LENGTH = 3
_MAX_SHORT_CODE_LENGTH = 64


def _normalize_site_domain_values(value: str | None) -> list[str]:
    raw = (value or "").replace(",", " ")
    candidates = [segment.strip() for segment in raw.split() if segment.strip()]
    normalized: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        lowered = candidate.lower()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            lowered = lowered.split("://", 1)[1]
        lowered = lowered.split("/", 1)[0]
        lowered = lowered.strip()
        if not lowered:
            continue
        if lowered in seen:
            continue
        normalized.append(lowered)
        seen.add(lowered)

    if not normalized:
        normalized.append(DEFAULT_SITE_DOMAIN)

    return normalized


def normalize_site_domain(value: str | None) -> str:
    return " ".join(_normalize_site_domain_values(value))


def split_site_domain_values(value: str | None) -> list[str]:
    return _normalize_site_domain_values(value)


def normalize_single_domain(value: str | None) -> str:
    values = _normalize_site_domain_values(value)
    return values[0] if values else DEFAULT_SITE_DOMAIN


def get_primary_site_domain(value: str | None) -> str:
    domains = split_site_domain_values(value)
    return domains[0] if domains else DEFAULT_SITE_DOMAIN


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


def resolve_short_link_hosts(settings: SiteSettings) -> set[str]:
    """Return hostnames that should trigger short link lookups."""

    hosts: set[str] = set()
    for domain in split_site_domain_values(settings.site_domain):
        canonical = domain.strip().lower()
        if not canonical:
            continue
        hosts.add(canonical)
        if canonical.startswith("www."):
            hosts.add(canonical[4:])
        else:
            hosts.add(f"www.{canonical}")

    return {host for host in hosts if host}


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


def _ensure_settings_table(db: Session) -> None:
    """Make sure the site settings table exists before selecting from it."""

    bind = db.get_bind() or engine
    # Restrict the create_all call to the site_settings table to avoid touching
    # unrelated schema. If the table already exists SQLAlchemy simply ignores it.
    Base.metadata.create_all(bind=bind, tables=[SiteSettings.__table__])


def get_site_settings(db: Session) -> SiteSettings:
    """Fetch the single settings row, creating one with defaults if necessary."""

    try:
        settings = db.scalar(select(SiteSettings).order_by(SiteSettings.id).limit(1))
    except (OperationalError, ProgrammingError):
        db.rollback()
        _ensure_settings_table(db)
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

    domain = get_primary_site_domain(settings.site_domain).strip().strip("/")
    return build_short_link_prefix_for_domain(settings, domain)


def build_short_link_prefix_for_domain(settings: SiteSettings, domain: str | None) -> str:
    """Compose the short link prefix for a specific managed domain."""

    normalized_domain = normalize_single_domain(domain).strip().strip("/")
    base_domain = normalized_domain or get_primary_site_domain(settings.site_domain)
    base_domain = base_domain.strip().strip("/")
    if not base_domain:
        base_domain = DEFAULT_SITE_DOMAIN
    base_url = f"https://{base_domain}".rstrip("/")
    path = settings.short_link_path
    if not path.startswith("/"):
        path = f"/{path}"
    if path != "/" and not path.endswith("/"):
        path = f"{path}/"
    return f"{base_url}{path}"


def build_short_link_ui_metadata(
    settings: SiteSettings, domain: str | None
) -> dict[str, str]:
    """Return display metadata for a short link domain."""

    normalized = normalize_single_domain(domain)
    prefix = build_short_link_prefix_for_domain(settings, normalized)
    display_prefix = prefix
    for scheme in ("https://", "http://"):
        if display_prefix.startswith(scheme):
            display_prefix = display_prefix[len(scheme) :]
            break
    if display_prefix.startswith(normalized):
        display_suffix = display_prefix[len(normalized) :]
    else:
        display_suffix = display_prefix
    return {
        "domain": normalized,
        "prefix": prefix,
        "display_prefix": display_prefix,
        "display_suffix": display_suffix,
    }


def match_short_link_domain(host: str, settings: SiteSettings) -> str | None:
    """Return the managed domain that matches a request host."""

    normalized_host = (host or "").strip().lower()
    if not normalized_host:
        return None

    managed = split_site_domain_values(settings.site_domain)
    for domain in managed:
        if normalized_host == domain:
            return domain
        if normalized_host == f"www.{domain}":
            return domain
        if domain.startswith("www.") and normalized_host == domain[4:]:
            return domain

    return None


def extract_short_link(path: str, settings: SiteSettings) -> tuple[str, str] | None:
    """Extract a short link code and remaining path based on configured prefix."""

    normalized_path = (path or "").lstrip("/")
    configured = settings.short_link_path
    if configured != "/":
        normalized_prefix = "/".join(
            segment for segment in configured.strip("/").split("/") if segment
        )
        if not normalized_prefix:
            normalized_prefix = ""
        if not normalized_path.startswith(normalized_prefix):
            return None
        remainder = normalized_path[len(normalized_prefix) :]
        if remainder.startswith("/"):
            remainder = remainder[1:]
        elif remainder:
            return None
    else:
        remainder = normalized_path

    if not remainder:
        return None

    code, _, extra = remainder.partition("/")
    if not code:
        return None
    return code, extra


def extract_short_code(path: str, settings: SiteSettings) -> str | None:
    """Backward compatible helper returning only the short link code."""

    match = extract_short_link(path, settings)
    if match is None:
        return None
    code, _ = match
    return code
