"""数据库模型与引擎配置。"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    func,
    inspect,
    text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/data.db")

DEFAULT_SITE_DOMAIN = "yet.la"
DEFAULT_SHORT_CODE_LENGTH = 6
DEFAULT_SHORT_LINK_PATH = "/"
DEFAULT_LOGO_URL = "https://img.811777.xyz/i/2025/10/04/68e0a00e3ab35.png"
DEFAULT_ICON_URL = "https://img.811777.xyz/i/2025/10/04/68e0a010486cf.png"


def _ensure_sqlite_directory(database_url: str) -> None:
    """Ensure the parent directory for a SQLite database exists."""

    url = make_url(database_url)
    if url.drivername != "sqlite":
        return

    database = url.database or ""
    if not database or database == ":memory:":
        return

    db_path = Path(database)
    parent = db_path.parent
    if parent.exists():
        return

    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - depends on environment permissions
        raise RuntimeError(
            f"无法创建 SQLite 数据目录: {parent!s}"
        ) from exc


_ensure_sqlite_directory(DATABASE_URL)


class Base(DeclarativeBase):
    """SQLAlchemy Declarative 基类。"""


engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class SiteSettings(Base):
    """站点配置，包含品牌与短链规则。"""

    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_domain: Mapped[str] = mapped_column(String(255), default=DEFAULT_SITE_DOMAIN, nullable=False)
    short_code_length: Mapped[int] = mapped_column(Integer, default=DEFAULT_SHORT_CODE_LENGTH, nullable=False)
    short_link_path: Mapped[str] = mapped_column(String(255), default=DEFAULT_SHORT_LINK_PATH, nullable=False)
    logo_url: Mapped[str] = mapped_column(String(2048), default=DEFAULT_LOGO_URL, nullable=False)
    icon_url: Mapped[str] = mapped_column(String(2048), default=DEFAULT_ICON_URL, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base):
    """系统用户表，支持管理员与普通用户。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    short_links: Mapped[list["ShortLink"]] = relationship(back_populates="owner")
    subdomain_redirects: Mapped[list["SubdomainRedirect"]] = relationship(
        back_populates="owner"
    )


class SubdomainRedirect(Base):
    """子域名重定向规则。"""

    __tablename__ = "subdomain_redirects"

    id: Mapped[int] = mapped_column(primary_key=True)
    host: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    target_url: Mapped[str] = mapped_column(String(2048))
    code: Mapped[int] = mapped_column("code_int", Integer, default=302, nullable=False)
    domain: Mapped[str] = mapped_column(
        String(255), default=DEFAULT_SITE_DOMAIN, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    hits: Mapped[int] = mapped_column("hits_int", Integer, default=0, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    owner: Mapped[User | None] = relationship(back_populates="subdomain_redirects")

    @property
    def owner_username(self) -> str | None:  # pragma: no cover - 简单访问器
        return self.owner.username if self.owner else None


class SubdomainBlacklist(Base):
    """禁止占用的子域前缀列表。"""

    __tablename__ = "subdomain_blacklist"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

class ShortLink(Base):
    """短链接记录表。"""

    __tablename__ = "short_links"
    __table_args__ = (
        UniqueConstraint("domain", "code", name="uq_short_links_domain_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    target_url: Mapped[str] = mapped_column(String(2048))
    hits: Mapped[int] = mapped_column("hits_int", Integer, default=0, nullable=False)
    domain: Mapped[str] = mapped_column(
        String(255), default=DEFAULT_SITE_DOMAIN, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    owner: Mapped[User | None] = relationship(back_populates="short_links")

    @property
    def owner_username(self) -> str | None:  # pragma: no cover - 简单访问器
        return self.owner.username if self.owner else None


def ensure_subdomain_hits_column() -> None:
    """Ensure the legacy databases have the hits column for subdomain redirects."""

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("subdomain_redirects")}
    if "hits_int" in columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE subdomain_redirects ADD COLUMN hits_int INTEGER NOT NULL DEFAULT 0")
        )


def ensure_user_association_columns() -> None:
    """Ensure legacy tables have user_id columns for ownership tracking."""

    inspector = inspect(engine)

    short_link_columns = {
        column["name"] for column in inspector.get_columns("short_links")
    }
    if "user_id" not in short_link_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE short_links ADD COLUMN user_id INTEGER REFERENCES users(id)")
            )

    subdomain_columns = {
        column["name"] for column in inspector.get_columns("subdomain_redirects")
    }
    if "user_id" not in subdomain_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE subdomain_redirects ADD COLUMN user_id INTEGER REFERENCES users(id)"
                )
            )


def ensure_domain_columns() -> None:
    """Ensure legacy tables include the domain columns and related indexes."""

    inspector = inspect(engine)

    short_link_columns = {
        column["name"] for column in inspector.get_columns("short_links")
    }
    if "domain" not in short_link_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE short_links ADD COLUMN domain VARCHAR(255) NOT NULL DEFAULT :default_domain"
                ),
                {"default_domain": DEFAULT_SITE_DOMAIN},
            )
    short_link_indexes = inspector.get_indexes("short_links")
    for index in short_link_indexes:
        columns = index.get("column_names", [])
        if index.get("unique") and columns == ["code"]:
            index_name = index.get("name")
            if index_name:
                with engine.begin() as connection:
                    connection.execute(
                        text(f'DROP INDEX IF EXISTS "{index_name}"')
                    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_short_links_domain_code ON short_links(domain, code)"
            )
        )

    subdomain_columns = {
        column["name"] for column in inspector.get_columns("subdomain_redirects")
    }
    if "domain" not in subdomain_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE subdomain_redirects ADD COLUMN domain VARCHAR(255) NOT NULL DEFAULT :default_domain"
                ),
                {"default_domain": DEFAULT_SITE_DOMAIN},
            )
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_subdomain_redirects_domain ON subdomain_redirects(domain)"
            )
        )

