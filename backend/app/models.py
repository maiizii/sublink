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
    select,
    text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/data.db")

DEFAULT_SITE_DOMAIN = "yet.la"
DEFAULT_SHORT_CODE_LENGTH = 6
DEFAULT_SHORT_LINK_PATH = "/"
DEFAULT_LOGO_URL = "https://img.811777.xyz/i/2025/10/09/68e7c2a2d4967.png"
DEFAULT_ICON_URL = "https://img.811777.xyz/i/2025/10/08/68e6364d2e46d.png"


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
    managed_domains: Mapped[str] = mapped_column(
        String(1024), default=DEFAULT_SITE_DOMAIN, nullable=False
    )
    short_code_length: Mapped[int] = mapped_column(Integer, default=DEFAULT_SHORT_CODE_LENGTH, nullable=False)
    short_link_path: Mapped[str] = mapped_column(String(255), default=DEFAULT_SHORT_LINK_PATH, nullable=False)
    logo_url: Mapped[str] = mapped_column(String(2048), default=DEFAULT_LOGO_URL, nullable=False)
    icon_url: Mapped[str] = mapped_column(String(2048), default=DEFAULT_ICON_URL, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def domain_list(self) -> list[str]:  # pragma: no cover - 简单访问器
        raw = (self.managed_domains or "").split()
        return [domain for domain in raw if domain]


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
    domain: Mapped[str] = mapped_column(String(255), default=DEFAULT_SITE_DOMAIN, nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(String(2048))
    code: Mapped[int] = mapped_column("code_int", Integer, default=302, nullable=False)
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
    domain: Mapped[str] = mapped_column(String(255), default=DEFAULT_SITE_DOMAIN, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    target_url: Mapped[str] = mapped_column(String(2048))
    hits: Mapped[int] = mapped_column("hits_int", Integer, default=0, nullable=False)
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


def _fetch_primary_domain(session: Session | None = None) -> str:
    """Read the primary managed domain from the settings table."""

    def _resolve(settings: SiteSettings | None) -> str:
        if settings is None:
            return DEFAULT_SITE_DOMAIN
        for candidate in (settings.managed_domains or "").split():
            stripped = candidate.strip().lower()
            if stripped:
                return stripped
        canonical = (settings.site_domain or "").strip().lower()
        return canonical or DEFAULT_SITE_DOMAIN

    if session is not None:
        settings = session.scalar(select(SiteSettings).order_by(SiteSettings.id).limit(1))
        return _resolve(settings)

    with SessionLocal() as local:
        settings = local.scalar(select(SiteSettings).order_by(SiteSettings.id).limit(1))
        return _resolve(settings)


def ensure_site_settings_domain_column() -> None:
    """Ensure the managed_domains column exists and is populated."""

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("site_settings")}
    if "managed_domains" in columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE site_settings ADD COLUMN managed_domains VARCHAR(1024)")
        )

    with SessionLocal() as session:
        settings_rows = session.scalars(select(SiteSettings)).all()
        for settings in settings_rows:
            primary = (settings.site_domain or DEFAULT_SITE_DOMAIN).strip().lower()
            settings.managed_domains = primary or DEFAULT_SITE_DOMAIN
            session.add(settings)
        session.commit()


def ensure_short_link_domain_column() -> None:
    """Ensure short links store domain information and use scoped uniqueness."""

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("short_links")}
    unique_constraints = inspector.get_unique_constraints("short_links")
    has_domain_column = "domain" in columns
    has_code_unique = any(constraint.get("column_names") == ["code"] for constraint in unique_constraints)

    dialect = engine.dialect.name
    default_domain = _fetch_primary_domain()

    if dialect == "sqlite":
        if not has_domain_column or has_code_unique:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE short_links RENAME TO short_links_old"))
                connection.execute(
                    text(
                        """
                        CREATE TABLE short_links (
                            id INTEGER NOT NULL PRIMARY KEY,
                            domain VARCHAR(255) NOT NULL,
                            code VARCHAR(64) NOT NULL,
                            target_url VARCHAR(2048),
                            hits_int INTEGER NOT NULL DEFAULT 0,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            user_id INTEGER,
                            CONSTRAINT uq_short_links_domain_code UNIQUE (domain, code),
                            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
                        )
                        """
                    )
                )

                if has_domain_column:
                    domain_source = (
                        "CASE WHEN COALESCE(TRIM(domain), '') = '' "
                        "THEN :default_domain ELSE LOWER(domain) END"
                    )
                else:
                    domain_source = ":default_domain"

                connection.execute(
                    text(
                        f"""
                        INSERT INTO short_links (id, domain, code, target_url, hits_int, created_at, user_id)
                        SELECT
                            id,
                            {domain_source},
                            code,
                            target_url,
                            hits_int,
                            created_at,
                            user_id
                        FROM short_links_old
                        """
                    ),
                    {"default_domain": default_domain},
                )

                connection.execute(text("DROP TABLE short_links_old"))
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_short_links_domain ON short_links (domain)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_short_links_code ON short_links (code)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_short_links_user_id ON short_links (user_id)"
                    )
                )
        return

    if not has_domain_column:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE short_links ADD COLUMN domain VARCHAR(255)"
                    " DEFAULT :default_domain"
                ),
                {"default_domain": default_domain},
            )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE short_links SET domain = :default_domain "
                    "WHERE domain IS NULL OR TRIM(domain) = ''"
                ),
                {"default_domain": default_domain},
            )
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE short_links ALTER COLUMN domain DROP DEFAULT")
            )

    if has_code_unique:
        for constraint in unique_constraints:
            if constraint.get("column_names") == ["code"]:
                name = constraint.get("name")
                if not name:
                    continue
                with engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE short_links DROP CONSTRAINT "{name}"'))

    constraints = inspector.get_unique_constraints("short_links")
    has_scoped_unique = any(
        sorted(constraint.get("column_names") or []) == ["code", "domain"]
        for constraint in constraints
    )
    if not has_scoped_unique:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE short_links "
                    "ADD CONSTRAINT uq_short_links_domain_code UNIQUE (domain, code)"
                )
            )

    with engine.begin() as connection:
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_short_links_domain ON short_links (domain)")
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_short_links_code ON short_links (code)")
        )


def ensure_subdomain_domain_column() -> None:
    """Ensure subdomain redirects store their base domain separately."""

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("subdomain_redirects")}
    if "domain" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE subdomain_redirects ADD COLUMN domain VARCHAR(255)")
            )

        default_domain = _fetch_primary_domain()
        with SessionLocal() as session:
            redirects = session.scalars(select(SubdomainRedirect)).all()
            for redirect in redirects:
                host = (redirect.host or "").strip().lower()
                domain = host.split(".", 1)[1] if "." in host else host
                redirect.domain = domain or default_domain
                session.add(redirect)
            session.commit()

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_subdomain_redirects_domain "
                "ON subdomain_redirects (domain)"
            )
        )

