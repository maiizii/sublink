"""Pydantic schema 定义。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .models import DEFAULT_ICON_URL, DEFAULT_LOGO_URL
from .settings_service import (
    normalize_asset_url,
    normalize_short_code_length,
    normalize_short_link_path,
    normalize_site_domain,
)
from .validators import normalize_slug


class SubdomainRedirectBase(BaseModel):
    host: str = Field(..., description="例如 api.yet.la")
    target_url: str = Field(..., description="完整跳转地址")
    code: int = Field(default=302, description="HTTP 状态码")

    @field_validator("host")
    @classmethod
    def _normalize_host(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("子域不能为空")
        parts = normalized.split(".", 1)
        prefix = normalize_slug(parts[0], field="子域")
        if len(parts) == 1:
            return prefix
        suffix = parts[1].strip()
        return f"{prefix}.{suffix}" if suffix else prefix

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: int) -> int:
        if value not in {301, 302}:
            raise ValueError("仅支持 301 或 302 重定向")
        return value


class SubdomainRedirect(SubdomainRedirectBase):
    id: int = Field(..., description="数据库主键")
    created_at: datetime = Field(..., description="创建时间")
    hits: int = Field(default=0, description="累计访问次数")
    user_id: int | None = Field(default=None, description="所属用户 ID")
    owner_username: str | None = Field(default=None, description="所属用户名")

    model_config = {"from_attributes": True}


class SubdomainRedirectCreate(SubdomainRedirectBase):
    pass


class SubdomainRedirectUpdate(SubdomainRedirectBase):
    pass


class SubdomainBlacklistBase(BaseModel):
    label: str = Field(..., description="子域前缀")

    @field_validator("label")
    @classmethod
    def _normalize_label(cls, value: str) -> str:
        return normalize_slug(value, field="子域")


class SubdomainBlacklist(SubdomainBlacklistBase):
    id: int = Field(..., description="数据库主键")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class SubdomainBlacklistCreate(SubdomainBlacklistBase):
    pass


class SubdomainBlacklistBulkUpdate(BaseModel):
    labels: str = Field("", description="以空格分隔的子域前缀列表")

    @field_validator("labels")
    @classmethod
    def _normalize_labels(cls, value: str) -> str:
        return " ".join(value.split())


class ShortLinkBase(BaseModel):
    target_url: str = Field(..., description="目标地址")


class ShortLinkCreate(ShortLinkBase):
    code: str | None = Field(default=None, description="短链编码，可为空自动生成")

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return normalize_slug(stripped, field="短链编码")


class ShortLink(ShortLinkBase):
    id: int = Field(..., description="数据库主键")
    code: str = Field(..., description="短链编码")
    hits: int = Field(default=0, description="访问次数")
    created_at: datetime = Field(..., description="创建时间")
    user_id: int | None = Field(default=None, description="所属用户 ID")
    owner_username: str | None = Field(default=None, description="所属用户名")

    model_config = {"from_attributes": True}


class ShortLinkUpdate(ShortLinkBase):
    code: str = Field(..., description="短链编码")

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("短链编码不能为空")
        return normalize_slug(stripped, field="短链编码")


class UserBase(BaseModel):
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱地址")

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        return normalize_slug(value, field="用户名")

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("邮箱不能为空")
        return normalized


class UserCreate(UserBase):
    password: str = Field(..., description="登录密码")
    is_admin: bool = Field(default=False, description="是否管理员")

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError("密码长度至少为 6 位")
        return value


class UserUpdate(UserBase):
    is_admin: bool = Field(default=False, description="是否管理员")
    password: str | None = Field(default=None, description="新密码，可选")

    @field_validator("password")
    @classmethod
    def _normalize_password(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) < 6:
            raise ValueError("密码长度至少为 6 位")
        return value


class User(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    current_password: str = Field(..., description="原密码")
    new_password: str = Field(..., description="新密码")
    confirm_password: str = Field(..., description="确认新密码")

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError("密码长度至少为 6 位")
        return value

    @field_validator("confirm_password")
    @classmethod
    def _validate_confirm(cls, value: str, info: ValidationInfo) -> str:
        new_password = info.data.get("new_password") if info.data else None
        if new_password is not None and value != new_password:
            raise ValueError("两次输入的密码不一致")
        return value


class SiteSettingsBase(BaseModel):
    site_domain: str = Field(
        ..., description="管理域名，可使用空格分隔多个，首个为主域名"
    )
    short_code_length: int = Field(..., ge=3, le=64, description="短链默认长度")
    short_link_path: str = Field(..., description="短链路径前缀，例如 / 或 /r/")
    logo_url: str = Field(..., description="LOGO 图片地址")
    icon_url: str = Field(..., description="网站 ICON 图片地址")

    @field_validator("site_domain")
    @classmethod
    def _normalize_domain(cls, value: str) -> str:
        return normalize_site_domain(value)

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
    updated_at: datetime | None = Field(default=None, description="最近更新时间")

    model_config = {"from_attributes": True}


class SiteSettingsUpdate(SiteSettingsBase):
    pass

