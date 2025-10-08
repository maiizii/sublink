"""Lightweight translation helpers for server-rendered templates."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

from jinja2 import pass_context

from . import zh_cn

DEFAULT_LOCALE = "zh-CN"

_LOCALE_MAP: dict[str, Mapping[str, Any]] = {
    "zh-CN": zh_cn.TRANSLATIONS,
}


def _resolve(translations: Mapping[str, Any], key: str) -> Any:
    """Resolve a dotted translation key within the provided dictionary."""

    value: Any = translations
    for segment in key.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(segment)
        if value is None:
            return None
    return value


@lru_cache(maxsize=16)
def _get_locale_translations(locale: str) -> Mapping[str, Any]:
    return _LOCALE_MAP.get(locale, _LOCALE_MAP[DEFAULT_LOCALE])


def translate(
    key: str,
    *,
    locale: str | None = None,
    default: str | None = None,
    **params: Any,
) -> str:
    """Translate a dotted key for the requested locale."""

    target_locale = locale or DEFAULT_LOCALE
    translations = _get_locale_translations(target_locale)
    value = _resolve(translations, key)
    if value is None:
        value = default if default is not None else key
    if isinstance(value, str):
        if params:
            try:
                value = value.format(**params)
            except (KeyError, ValueError):
                # Fall back to the untranslated string when formatting fails.
                pass
        return value
    if isinstance(value, Mapping):
        # Returning a mapping allows templates to access nested namespaces.
        return dict(value)
    return str(value)


def get_namespace(key: str, *, locale: str | None = None) -> Mapping[str, Any]:
    """Return a nested translation namespace as a plain dictionary."""

    target_locale = locale or DEFAULT_LOCALE
    translations = _get_locale_translations(target_locale)
    value = _resolve(translations, key)
    if isinstance(value, Mapping):
        return dict(value)
    return {}


@pass_context
def jinja_translate(context, key: str, **params: Any) -> str:  # type: ignore[override]
    """Expose translations to Jinja templates via the ``_`` helper."""

    default = params.pop("default", None)
    locale = context.get("locale") if isinstance(context, Mapping) else None
    if not isinstance(locale, str) or not locale:
        locale = DEFAULT_LOCALE
    return translate(key, locale=locale, default=default, **params)


@pass_context
def jinja_namespace(context, key: str, **params: Any) -> Mapping[str, Any]:  # type: ignore[override]
    """Return a translation namespace that is aware of the template locale."""

    locale_param = params.get("locale")
    locale = (
        locale_param
        if isinstance(locale_param, str) and locale_param
        else context.get("locale")
        if isinstance(context, Mapping)
        else None
    )
    if not isinstance(locale, str) or not locale:
        locale = DEFAULT_LOCALE
    return get_namespace(key, locale=locale)
