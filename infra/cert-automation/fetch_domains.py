"""Resolve managed domains from SubLink settings for certificate issuance."""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from contextlib import closing
from typing import Iterable, Set

EXIT_DB_NOT_READY = 10
EXIT_NO_DOMAINS = 12
DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?!-)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$",
    re.IGNORECASE,
)


def _canonicalize(raw: str | None) -> str | None:
    if not raw:
        return None

    candidate = raw.strip().lower()
    if not candidate:
        return None

    if "//" in candidate:
        candidate = candidate.split("//", 1)[1]

    if ":" in candidate:
        candidate = candidate.split(":", 1)[0]

    candidate = candidate.strip("./")

    if candidate.startswith("*."):
        candidate = candidate[2:]

    if not candidate:
        return None

    try:
        candidate = candidate.encode("idna").decode("ascii")
    except Exception:
        return None

    if DOMAIN_PATTERN.match(candidate):
        return candidate

    return None


def _extract_domains(raw: str | None) -> Iterable[str]:
    if not raw:
        return []

    normalized = raw.replace(",", " ")
    return [token for token in (item.strip() for item in normalized.split()) if token]


def _resolve_sqlite_path(database_url: str) -> str | None:
    if not database_url.startswith("sqlite:"):
        return None

    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        path = database_url[len(prefix) :]
    else:
        path = database_url[len("sqlite:") :]

    if not path.startswith("/"):
        path = "/" + path

    return path


def _load_from_database(path: str) -> Iterable[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT site_domain, managed_domains FROM site_settings ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if not row:
        return []

    domains: Set[str] = set()

    site_domain = _canonicalize(row["site_domain"])
    if site_domain:
        domains.add(site_domain)

    for candidate in _extract_domains(row["managed_domains"]):
        normalized = _canonicalize(candidate)
        if normalized:
            domains.add(normalized)

    return domains


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "sqlite:////data/data.db")
    base_domain = os.getenv("BASE_DOMAIN", "")
    extra_domains = os.getenv("CERTBOT_ADDITIONAL_DOMAINS", "")

    domains: Set[str] = set()

    for source in (base_domain, extra_domains):
        for token in _extract_domains(source):
            normalized = _canonicalize(token)
            if normalized:
                domains.add(normalized)

    sqlite_path = _resolve_sqlite_path(database_url)

    if sqlite_path:
        try:
            for candidate in _load_from_database(sqlite_path):
                domains.add(candidate)
        except FileNotFoundError:
            if not domains:
                return EXIT_DB_NOT_READY
        except sqlite3.Error as exc:  # pragma: no cover - defensive logging
            print(f"failed to query site_settings: {exc}", file=sys.stderr)
            if not domains:
                return EXIT_DB_NOT_READY

    if not domains:
        print("no domains configured", file=sys.stderr)
        return EXIT_NO_DOMAINS

    for domain in sorted(domains):
        print(domain)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
