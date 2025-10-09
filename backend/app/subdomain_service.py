"""Helpers for managing subdomain blacklist defaults and utilities."""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import select

from .i18n import translate
from .locale import get_current_locale
from .models import SessionLocal, SubdomainBlacklist
from .validators import normalize_slug


def _t(key: str) -> str:
    return translate(key, locale=get_current_locale())


DEFAULT_SUBDOMAIN_BLACKLIST_LABELS: tuple[str, ...] = (
    "www",
    "mail",
    "ftp",
    "smtp",
    "imap",
    "pop",
    "api",
    "admin",
    "root",
    "sys",
    "dns",
    "ns1",
    "ns2",
    "server",
    "gateway",
    "proxy",
    "router",
    "test",
    "sandbox",
    "staging",
    "beta",
    "status",
    "static",
    "cdn",
    "ssl",
    "secure",
    "login",
    "signup",
    "register",
    "account",
    "user",
    "support",
    "helpdesk",
    "contact",
    "pay",
    "wallet",
    "billing",
    "invoice",
    "bank",
    "auth",
    "verify",
    "identity",
    "google",
    "facebook",
    "twitter",
    "apple",
    "amazon",
    "microsoft",
    "paypal",
    "openai",
    "localhost",
    "example",
    "invalid",
    "internal",
    "local",
    "lan",
    "home",
    "loopback",
)


def ensure_default_subdomain_blacklist() -> None:
    """Ensure the default blacklist labels exist in the database."""

    with SessionLocal() as session:
        existing = {label for label in session.scalars(select(SubdomainBlacklist.label))}
        missing = [
            normalize_slug(label, field=_t("admin.fields.subdomainPrefix"))
            for label in DEFAULT_SUBDOMAIN_BLACKLIST_LABELS
            if label not in existing
        ]
        if not missing:
            return
        session.add_all(SubdomainBlacklist(label=label) for label in missing)
        session.commit()


def format_blacklist_labels(labels: Iterable[SubdomainBlacklist]) -> str:
    """Join blacklist labels into a single space separated string."""

    return " ".join(entry.label for entry in labels)

