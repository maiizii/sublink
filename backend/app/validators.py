"""Reusable validation helpers for slug-like identifiers."""
from __future__ import annotations

import re


_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def normalize_slug(value: str, *, field: str, enforce_length: bool = False) -> str:
    """Normalize and validate a slug value.

    Slugs must consist of lowercase letters, digits, or hyphens, start and end
    with an alphanumeric character, and be 3-20 characters long.
    """

    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{field}不能为空")
    if not _SLUG_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field}仅允许小写字母、数字或连字符，且首尾需为字母或数字")
    if enforce_length and not 3 <= len(normalized) <= 20:
        raise ValueError(f"{field}长度需为 3-20 个字符")
    return normalized


def extract_subdomain_label(host: str) -> str:
    """Return the leading label of a host for blacklist enforcement."""

    normalized = host.strip().lower()
    if not normalized:
        return ""
    return normalized.split(".", 1)[0]


def normalize_domain(value: str, *, allow_empty: bool = False) -> str:
    """Normalize a domain value by stripping schemes, paths and upper-case letters."""

    raw = (value or "").strip().lower()
    if raw.startswith("http://") or raw.startswith("https://"):
        raw = raw.split("://", 1)[1]
    if "/" in raw:
        raw = raw.split("/", 1)[0]
    normalized = raw.strip()
    if not normalized:
        if allow_empty:
            return ""
        raise ValueError("域名不能为空")
    return normalized

