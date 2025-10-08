"""Reusable validation helpers for slug-like identifiers."""
from __future__ import annotations

import re

from .i18n import DEFAULT_LOCALE, translate


_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def _t(key: str, **params: str) -> str:
    return translate(key, locale=DEFAULT_LOCALE, **params)


def normalize_slug(value: str, *, field: str, enforce_length: bool = False) -> str:
    """Normalize and validate a slug value.

    Slugs must consist of lowercase letters, digits, or hyphens, start and end
    with an alphanumeric character, and be 3-20 characters long.
    """

    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(_t("admin.validation.slugEmpty", field=field))
    if not _SLUG_PATTERN.fullmatch(normalized):
        raise ValueError(_t("admin.validation.slugInvalid", field=field))
    if enforce_length and not 3 <= len(normalized) <= 20:
        raise ValueError(_t("admin.validation.slugLengthRange", field=field))
    return normalized


def extract_subdomain_label(host: str) -> str:
    """Return the leading label of a host for blacklist enforcement."""

    normalized = host.strip().lower()
    if not normalized:
        return ""
    return normalized.split(".", 1)[0]

