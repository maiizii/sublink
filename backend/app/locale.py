"""Locale resolution helpers and request-scoped storage."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional, Tuple

from fastapi import Request

from .i18n import DEFAULT_LOCALE

SUPPORTED_LOCALES = {"zh-CN", "en-US"}
_CANONICAL_LOCALES = {code.lower(): code for code in SUPPORTED_LOCALES}
_LOCALE_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "zh_hans": "zh-CN",
    "en": "en-US",
    "en-us": "en-US",
    "en_us": "en-US",
}

LOCALE_COOKIE_NAME = "sublink-admin-locale"
LOCALE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365

_current_locale: ContextVar[str] = ContextVar(
    "sublink_current_locale", default=DEFAULT_LOCALE
)


def normalize_locale(value: Optional[str]) -> Optional[str]:
    """Normalize incoming locale strings to supported codes."""

    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    lowered = raw.lower().replace("_", "-")
    if lowered in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[lowered]
    if lowered in _CANONICAL_LOCALES:
        return _CANONICAL_LOCALES[lowered]
    if raw in SUPPORTED_LOCALES:
        return raw
    return None


def resolve_locale_from_request(request: Request) -> Tuple[str, bool]:
    """Resolve locale from query parameter, cookie, or default."""

    requested = normalize_locale(request.query_params.get("lang"))
    if requested:
        return requested, True
    from_cookie = normalize_locale(request.cookies.get(LOCALE_COOKIE_NAME))
    if from_cookie:
        return from_cookie, False
    return DEFAULT_LOCALE, True


def push_locale(value: str):
    """Activate a locale for the current context."""

    return _current_locale.set(value or DEFAULT_LOCALE)


def reset_locale(token) -> None:
    """Restore the locale context to the previous value."""

    _current_locale.reset(token)


def get_current_locale() -> str:
    """Return the locale associated with the current request context."""

    return _current_locale.get()
