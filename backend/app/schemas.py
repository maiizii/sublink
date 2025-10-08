"""Pydantic schema 定义。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .i18n import DEFAULT_LOCALE, translate
from .models import DEFAULT_ICON_URL, DEFAULT_LOGO_URL
from .settings_service import (
    normalize_asset_url,
    normalize_managed_domains,
    normalize_short_code_length,
    normalize_short_link_path,
    normalize_site_domain,
)
from .validators import normalize_slug


def _t(key: str, **params: Any) -> str:
    return translate(key, locale=DEFAULT_LOCALE, **params)


class SubdomainRedirectBase(BaseModel):
    host: str = Field(..., description=_t("admin.schemas.descriptions.subdomainHost"))
    target_url: str = Field(..., description=_t("admin.schemas.descriptions.targetUrl"))
    code: int = Field(default=302, description=_t("admin.schemas.descriptions.statusCode"))

    @field_validator("host")
    @classmethod
    def _normalize_host(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError(
                _t(
                    "admin.validation.fieldRequiredWithName",
                    field=_t("admin.fields.subdomain"),
                )
            )
        parts = normalized.split(".", 1)
        prefix = normalize_slug(parts[0], field=_t("admin.fields.subdomainPrefix"))
        if len(parts) == 1:
            return prefix
        suffix = parts[1].strip()
        return f"{prefix}.{suffix}" if suffix else prefix

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: int) -> int:
        if value not in {301, 302}:
            raise ValueError(_t("admin.validation.redirectStatusCode"))
        return value


class SubdomainRedirect(SubdomainRedirectBase):
    id: int = Field(..., description=_t("admin.schemas.descriptions.databaseId"))
    domain: str = Field(..., description=_t("admin.schemas.descriptions.subdomainDomain"))
    created_at: datetime = Field(..., description=_t("admin.schemas.descriptions.createdAt"))
    hits: int = Field(default=0, description=_t("admin.schemas.descriptions.visitCount"))
    user_id: int | None = Field(default=None, description=_t("admin.schemas.descriptions.userId"))
    owner_username: str | None = Field(
        default=None, description=_t("admin.schemas.descriptions.ownerUsername")
    )

    model_config = {"from_attributes": True}


class SubdomainRedirectCreate(SubdomainRedirectBase):
    pass


class SubdomainRedirectUpdate(SubdomainRedirectBase):
    pass


class SubdomainBlacklistBase(BaseModel):
    label: str = Field(
        ..., description=_t("admin.schemas.descriptions.subdomainLabel")
    )

    @field_validator("label")
    @classmethod
    def _normalize_label(cls, value: str) -> str:
        return normalize_slug(value, field=_t("admin.fields.subdomainPrefix"))


class SubdomainBlacklist(SubdomainBlacklistBase):
    id: int = Field(..., description=_t("admin.schemas.descriptions.databaseId"))
    created_at: datetime = Field(..., description=_t("admin.schemas.descriptions.createdAt"))

    model_config = {"from_attributes": True}


class SubdomainBlacklistCreate(SubdomainBlacklistBase):
    pass


class SubdomainBlacklistBulkUpdate(BaseModel):
    labels: str = Field(
        "",
        description=_t("admin.schemas.descriptions.blacklistLabels"),
    )

    @field_validator("labels")
    @classmethod
    def _normalize_labels(cls, value: str) -> str:
        return " ".join(value.split())


class ShortLinkBase(BaseModel):
    target_url: str = Field(
        ..., description=_t("admin.schemas.descriptions.targetUrl")
    )


class ShortLinkCreate(ShortLinkBase):
    code: str | None = Field(
        default=None, description=_t("admin.schemas.descriptions.shortLinkCodeOptional")
    )
    domain: str | None = Field(
        default=None,
        description=_t("admin.schemas.descriptions.shortLinkDomainOptional"),
    )

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return normalize_slug(stripped, field=_t("admin.fields.shortLinkCode"))

    @field_validator("domain")
    @classmethod
    def _normalize_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return normalize_site_domain(stripped)


class ShortLink(ShortLinkBase):
    id: int = Field(..., description=_t("admin.schemas.descriptions.databaseId"))
    code: str = Field(..., description=_t("admin.schemas.descriptions.shortLinkCode"))
    domain: str = Field(..., description=_t("admin.schemas.descriptions.domain"))
    hits: int = Field(default=0, description=_t("admin.schemas.descriptions.visits"))
    created_at: datetime = Field(..., description=_t("admin.schemas.descriptions.createdAt"))
    user_id: int | None = Field(default=None, description=_t("admin.schemas.descriptions.userId"))
    owner_username: str | None = Field(
        default=None, description=_t("admin.schemas.descriptions.ownerUsername")
    )

    model_config = {"from_attributes": True}


class ShortLinkUpdate(ShortLinkBase):
    code: str = Field(..., description=_t("admin.schemas.descriptions.shortLinkCode"))
    domain: str | None = Field(
        default=None,
        description=_t("admin.schemas.descriptions.shortLinkDomainKeep"),
    )

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(
                _t(
                    "admin.validation.fieldRequiredWithName",
                    field=_t("admin.fields.shortLinkCode"),
                )
            )
        return normalize_slug(stripped, field=_t("admin.fields.shortLinkCode"))

    @field_validator("domain")
    @classmethod
    def _normalize_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return normalize_site_domain(stripped)


class UserBase(BaseModel):
    username: str = Field(..., description=_t("admin.schemas.descriptions.username"))
    email: str = Field(..., description=_t("admin.schemas.descriptions.email"))

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        return normalize_slug(value, field=_t("admin.fields.username"))

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(
                _t(
                    "admin.validation.fieldRequiredWithName",
                    field=_t("admin.fields.email"),
                )
            )
        return normalized


class UserCreate(UserBase):
    password: str = Field(..., description=_t("admin.schemas.descriptions.password"))
    is_admin: bool = Field(default=False, description=_t("admin.schemas.descriptions.isAdmin"))

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError(
                _t(
                    "admin.validation.passwordMinLength",
                    field=_t("admin.fields.password"),
                    min=6,
                )
            )
        return value


class UserUpdate(UserBase):
    is_admin: bool = Field(default=False, description=_t("admin.schemas.descriptions.isAdmin"))
    password: str | None = Field(
        default=None, description=_t("admin.schemas.descriptions.passwordOptional")
    )

    @field_validator("password")
    @classmethod
    def _normalize_password(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) < 6:
            raise ValueError(
                _t(
                    "admin.validation.passwordMinLength",
                    field=_t("admin.fields.newPassword"),
                    min=6,
                )
            )
        return value


class User(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    current_password: str = Field(
        ..., description=_t("admin.schemas.descriptions.passwordCurrent")
    )
    new_password: str = Field(
        ..., description=_t("admin.schemas.descriptions.passwordNew")
    )
    confirm_password: str = Field(
        ..., description=_t("admin.schemas.descriptions.passwordConfirm")
    )

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError(
                _t(
                    "admin.validation.passwordMinLength",
                    field=_t("admin.fields.newPassword"),
                    min=6,
                )
            )
        return value

    @field_validator("confirm_password")
    @classmethod
    def _validate_confirm(cls, value: str, info: ValidationInfo) -> str:
        new_password = info.data.get("new_password") if info.data else None
        if new_password is not None and value != new_password:
            raise ValueError(_t("admin.validation.passwordMismatch"))
        return value


class SiteSettingsBase(BaseModel):
    managed_domains: str = Field(
        ..., description=_t("admin.schemas.descriptions.managedDomains")
    )
    short_code_length: int = Field(
        ...,
        ge=3,
        le=64,
        description=_t("admin.schemas.descriptions.shortCodeLength"),
    )
    short_link_path: str = Field(
        ..., description=_t("admin.schemas.descriptions.shortLinkPath")
    )
    logo_url: str = Field(..., description=_t("admin.schemas.descriptions.logoUrl"))
    icon_url: str = Field(..., description=_t("admin.schemas.descriptions.iconUrl"))

    @field_validator("managed_domains")
    @classmethod
    def _normalize_domains(cls, value: str) -> str:
        domains = normalize_managed_domains(value)
        return " ".join(domains)

    @field_validator("short_code_length")
    @classmethod
    def _normalize_length(cls, value: int) -> int:
        return normalize_short_code_length(value)

    @field_validator("short_link_path")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        return normalize_short_link_path(value)

    @field_validator("logo_url")
    @classmethod
    def _normalize_logo(cls, value: str) -> str:
        return normalize_asset_url(value, DEFAULT_LOGO_URL)

    @field_validator("icon_url")
    @classmethod
    def _normalize_icon(cls, value: str) -> str:
        return normalize_asset_url(value, DEFAULT_ICON_URL)


class SiteSettings(SiteSettingsBase):
    site_domain: str = Field(..., description=_t("admin.schemas.descriptions.siteDomain"))
    updated_at: datetime | None = Field(
        default=None, description=_t("admin.schemas.descriptions.updatedAt")
    )

    @field_validator("site_domain")
    @classmethod
    def _normalize_domain(cls, value: str) -> str:
        return normalize_site_domain(value)

    model_config = {"from_attributes": True}


class SiteSettingsUpdate(SiteSettingsBase):
    pass

