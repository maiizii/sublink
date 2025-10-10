from __future__ import annotations

from backend.app.models import SessionLocal
from backend.app.settings_service import get_site_settings

ADMIN_AUTH = ("admin", "admin")


def test_create_short_link(client: "SimpleClient") -> None:
    response = client.post(
        "/api/links",
        json={"target_url": "https://example.com"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["target_url"] == "https://example.com"
    assert payload["code"]
    assert payload["hits"] == 0
    assert payload["domain"] == "yet.la"


def test_create_short_link_conflict(client: "SimpleClient") -> None:
    client.post(
        "/api/links",
        json={"target_url": "https://example.com", "code": "custom"},
        auth=ADMIN_AUTH,
    )

    conflict = client.post(
        "/api/links",
        json={"target_url": "https://example.org", "code": "custom"},
        auth=ADMIN_AUTH,
    )
    assert conflict.status_code == 409
    assert conflict.json() == {"error": "短链接编码已存在"}


def test_create_short_link_allows_same_code_different_domain(client: "SimpleClient") -> None:
    original = client.get("/api/settings", auth=ADMIN_AUTH).json()

    update = client.put(
        "/api/settings",
        data={
            "managed_domains": "yet.la go2.you",
            "short_code_length": "6",
            "short_link_path": "/",
            "logo_url": "https://img.example.com/logo.png",
            "icon_url": "https://img.example.com/icon.png",
        },
        auth=ADMIN_AUTH,
    )
    assert update.status_code == 200

    first = client.post(
        "/api/links",
        json={"target_url": "https://example.com", "code": "dup", "domain": "yet.la"},
        auth=ADMIN_AUTH,
    )
    assert first.status_code == 201
    second = client.post(
        "/api/links",
        json={"target_url": "https://example.org", "code": "dup", "domain": "go2.you"},
        auth=ADMIN_AUTH,
    )
    assert second.status_code == 201
    assert first.json()["domain"] == "yet.la"
    assert second.json()["domain"] == "go2.you"

    reset = client.put("/api/settings", json=original, auth=ADMIN_AUTH)
    assert reset.status_code == 200


def test_create_short_link_invalid_code(client: "SimpleClient") -> None:
    response = client.post(
        "/api/links",
        json={"target_url": "https://example.com", "code": "-bad"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert any("短链编码" in item.get("msg", "") for item in detail)


def test_admin_allows_long_short_code(client: "SimpleClient") -> None:
    long_code = "adminlongshortcodevalue-1234567890"
    response = client.post(
        "/api/links",
        json={"target_url": "https://example.com/admin", "code": long_code},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 201
    created = response.json()
    assert created["code"] == long_code

    client.delete(f"/api/links/{created['id']}", auth=ADMIN_AUTH)


def test_non_admin_short_code_length_enforced(client: "SimpleClient") -> None:
    client.post(
        "/api/users",
        json={
            "username": "shortuser",
            "email": "shortuser@example.com",
            "password": "shortpass",
            "is_admin": False,
        },
        auth=ADMIN_AUTH,
    )
    user_auth = ("shortuser", "shortpass")

    denied = client.post(
        "/api/links",
        json={"target_url": "https://example.com/nonadmin", "code": "ab"},
        auth=user_auth,
    )
    assert denied.status_code == 422
    assert denied.json() == {"detail": "短链编码长度需为 3-20 个字符"}


def test_redirect_short_link_and_hits(client: "SimpleClient") -> None:
    client.post(
        "/api/links",
        json={"target_url": "https://example.com/landing", "code": "go1"},
        auth=ADMIN_AUTH,
    )

    redirect = client.get("/go1", headers={"host": "yet.la"}, follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://example.com/landing"

    listing = client.get("/api/links", auth=ADMIN_AUTH)
    assert listing.status_code == 200
    records = listing.json()
    assert len(records) == 1
    assert records[0]["hits"] == 1


def test_short_link_redirect_with_extra_path_and_query(client: "SimpleClient") -> None:
    client.post(
        "/api/links",
        json={"target_url": "https://docs.example.com", "code": "docs"},
        auth=ADMIN_AUTH,
    )

    response = client.get(
        "/docs/guide/v1/?lang=zh",
        headers={"host": "yet.la"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "https://docs.example.com/guide/v1/?lang=zh"


def test_short_link_with_same_host_drops_extra_path(client: "SimpleClient") -> None:
    client.post(
        "/api/links",
        json={"target_url": "https://yet.la/welcome/", "code": "welcome"},
        auth=ADMIN_AUTH,
    )

    response = client.get(
        "/welcome/docs?ref=test",
        headers={"host": "yet.la"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "https://yet.la/welcome/?ref=test"


def test_redirect_short_link_with_admin_prefix(client: "SimpleClient") -> None:
    update = client.put(
        "/api/settings",
        data={
            "managed_domains": "yet.la",
            "short_code_length": "6",
            "short_link_path": "/admin/",
            "logo_url": "https://img.example.com/logo.png",
            "icon_url": "https://img.example.com/icon.png",
        },
        auth=ADMIN_AUTH,
    )
    assert update.status_code == 200

    create = client.post(
        "/api/links",
        json={"target_url": "https://example.org/landing", "code": "promo"},
        auth=ADMIN_AUTH,
    )
    assert create.status_code == 201

    redirect = client.get(
        "/admin/promo",
        headers={"host": "yet.la"},
        follow_redirects=False,
    )
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://example.org/landing"


def test_short_link_redirect_handles_www_host(client: "SimpleClient") -> None:
    client.post(
        "/api/links",
        json={"target_url": "https://example.net/home", "code": "promo"},
        auth=ADMIN_AUTH,
    )

    client.post(
        "/api/subdomains",
        json={
            "host": "www.yet.la",
            "target_url": "https://yet.la/admin",
            "code": 302,
        },
        auth=ADMIN_AUTH,
    )

    redirect = client.get(
        "/promo",
        headers={"host": "www.yet.la"},
        follow_redirects=False,
    )
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://example.net/home"


def test_redirect_short_link_not_found(client: "SimpleClient") -> None:
    response = client.get("/missing", headers={"host": "yet.la"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://yet.la"


def test_missing_short_link_with_path_avoids_subdomain_loop(
    client: "SimpleClient",
) -> None:
    update = client.put(
        "/api/settings",
        data={
            "managed_domains": "https://www.example.com",
            "short_code_length": "6",
            "short_link_path": "/g/",
            "logo_url": "https://img.example.com/logo.png",
            "icon_url": "https://img.example.com/icon.png",
        },
        auth=ADMIN_AUTH,
    )
    assert update.status_code == 200

    client.post(
        "/api/subdomains",
        json={
            "host": "www.example.com",
            "target_url": "https://www.example.com/admin",
            "code": 302,
        },
        auth=ADMIN_AUTH,
    )

    response = client.get(
        "/gfsdf/gfd",
        headers={"host": "www.example.com"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "https://www.example.com"


def test_root_request_redirects_to_admin(client: "SimpleClient") -> None:
    response = client.get("/", headers={"host": "yet.la"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://yet.la/admin"


def test_short_link_root_still_not_found(client: "SimpleClient") -> None:
    with SessionLocal() as db:
        settings = get_site_settings(db)
        original = {
            "managed_domains": settings.managed_domains,
            "short_code_length": settings.short_code_length,
            "short_link_path": settings.short_link_path,
            "logo_url": settings.logo_url,
            "icon_url": settings.icon_url,
        }

    payload = dict(original)
    payload["managed_domains"] = "yet.la go2.you"
    update = client.put("/api/settings", json=payload, auth=ADMIN_AUTH)
    assert update.status_code == 200

    response = client.get("/", headers={"host": "go2.you"}, follow_redirects=False)
    assert response.status_code == 404

    reset = client.put("/api/settings", json=original, auth=ADMIN_AUTH)
    assert reset.status_code == 200


def test_create_short_link_via_htmx_form(client: "SimpleClient") -> None:
    response = client.post(
        "/api/links",
        data={"target_url": "https://example.com/docs"},
        headers={"hx-request": "true"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 201
    assert response.headers.get("hx-trigger") == "refresh-links"
    assert "短链创建成功" in response.text


def test_delete_short_link_via_htmx_button(client: "SimpleClient") -> None:
    created = client.post(
        "/api/links",
        json={"target_url": "https://example.com/remove", "code": "temp"},
        auth=ADMIN_AUTH,
    )
    link_id = created.json()["id"]

    response = client.delete(
        f"/api/links/{link_id}",
        headers={"hx-request": "true"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 200
    assert response.headers.get("hx-trigger") == "refresh-links"
    assert "短链已删除" in response.text


def test_update_short_link_via_htmx_form(client: "SimpleClient") -> None:
    created = client.post(
        "/api/links",
        json={"target_url": "https://example.com/edit", "code": "orig"},
        auth=ADMIN_AUTH,
    ).json()

    response = client.put(
        f"/api/links/{created['id']}",
        data={"code": "updated", "target_url": "https://example.com/new"},
        headers={"hx-request": "true"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 200
    assert response.headers.get("hx-trigger") == "refresh-links"
    assert "短链已更新" in response.text
    assert "short-link-row" in response.text
    assert "hx-swap-oob=\"outerHTML\"" in response.text

    listing = client.get("/api/links", auth=ADMIN_AUTH)
    records = listing.json()
    assert records[0]["code"] == "updated"
    assert records[0]["target_url"] == "https://example.com/new"


def test_admin_short_link_partials(client: "SimpleClient") -> None:
    client.post(
        "/api/links",
        json={"target_url": "https://example.com/list", "code": "list"},
        auth=ADMIN_AUTH,
    )

    table = client.get("/admin/links/table", auth=ADMIN_AUTH)
    assert table.status_code == 200
    assert "<th scope=\"col\">短链</th>" in table.text
    assert "<th scope=\"col\">用户</th>" in table.text

    count = client.get("/admin/links/count", auth=ADMIN_AUTH)
    assert count.status_code == 200
    assert "short-link-count" in count.text


def test_short_link_edit_preserves_unmanaged_domain_option(
    client: "SimpleClient",
) -> None:
    update = client.put(
        "/api/settings",
        data={
            "managed_domains": "go2.you yet.la",
            "short_code_length": "6",
            "short_link_path": "/",
            "logo_url": "https://img.example.com/logo.png",
            "icon_url": "https://img.example.com/icon.png",
        },
        auth=ADMIN_AUTH,
    )
    assert update.status_code == 200

    created = client.post(
        "/api/links",
        json={
            "target_url": "https://example.com/preserved",
            "code": "keep",
            "domain": "yet.la",
        },
        auth=ADMIN_AUTH,
    ).json()

    removal = client.put(
        "/api/settings",
        data={
            "managed_domains": "go2.you",
            "short_code_length": "6",
            "short_link_path": "/",
            "logo_url": "https://img.example.com/logo.png",
            "icon_url": "https://img.example.com/icon.png",
        },
        auth=ADMIN_AUTH,
    )
    assert removal.status_code == 200

    edit_row = client.get(f"/admin/links/{created['id']}/edit", auth=ADMIN_AUTH)
    assert edit_row.status_code == 200
    assert '<option\n                value="yet.la"' in edit_row.text
    assert "selected\n                hidden" in edit_row.text
    assert 'data-display="yet.la/"' in edit_row.text


def test_short_links_are_scoped_by_user(client: "SimpleClient") -> None:
    client.post(
        "/api/links",
        json={"target_url": "https://example.com/admin", "code": "admin-link"},
        auth=ADMIN_AUTH,
    )

    client.post(
        "/api/users",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "alicepass",
            "is_admin": False,
        },
        auth=ADMIN_AUTH,
    )

    normal_auth = ("alice", "alicepass")
    client.post(
        "/api/links",
        json={"target_url": "https://example.com/alice", "code": "alice"},
        auth=normal_auth,
    )

    normal_listing = client.get("/api/links", auth=normal_auth)
    assert normal_listing.status_code == 200
    normal_records = normal_listing.json()
    assert len(normal_records) == 1
    assert normal_records[0]["code"] == "alice"

    admin_listing = client.get("/api/links", auth=ADMIN_AUTH)
    assert admin_listing.status_code == 200
    admin_codes = {record["code"] for record in admin_listing.json()}
    assert admin_codes == {"admin-link", "alice"}


def test_admin_only_domain_hidden_from_normal_users(client: "SimpleClient") -> None:
    update = client.put(
        "/api/settings",
        data={
            "managed_domains": "go2.you yet.la* tkgo.de",
            "short_code_length": "6",
            "short_link_path": "/",
            "logo_url": "https://img.example.com/logo.png",
            "icon_url": "https://img.example.com/icon.png",
        },
        auth=ADMIN_AUTH,
    )
    assert update.status_code == 200
    assert update.json()["managed_domains"] == "go2.you yet.la* tkgo.de"

    client.post(
        "/api/users",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "alicepass",
            "is_admin": False,
        },
        auth=ADMIN_AUTH,
    )

    normal_auth = ("alice", "alicepass")
    forbidden = client.post(
        "/api/links",
        json={
            "target_url": "https://example.com/alice",
            "code": "alice-admin",
            "domain": "yet.la",
        },
        auth=normal_auth,
    )
    assert forbidden.status_code == 422
    assert forbidden.json() == {"detail": "域名不在管理列表中"}

    allowed = client.post(
        "/api/links",
        json={
            "target_url": "https://example.com/alice",
            "code": "alice-public",
            "domain": "tkgo.de",
        },
        auth=normal_auth,
    )
    assert allowed.status_code == 201
    assert allowed.json()["domain"] == "tkgo.de"

    admin_link = client.post(
        "/api/links",
        json={
            "target_url": "https://example.com/admin",
            "code": "admin-only",
            "domain": "yet.la",
        },
        auth=ADMIN_AUTH,
    )
    assert admin_link.status_code == 201
    assert admin_link.json()["domain"] == "yet.la"


def test_admin_only_domain_keeps_existing_links_visible(client: "SimpleClient") -> None:
    original = client.get("/api/settings", auth=ADMIN_AUTH).json()

    update = client.put(
        "/api/settings",
        data={
            "managed_domains": "911777.xyz tkgo.de",
            "short_code_length": str(original["short_code_length"]),
            "short_link_path": original["short_link_path"],
            "logo_url": original["logo_url"],
            "icon_url": original["icon_url"],
        },
        auth=ADMIN_AUTH,
    )
    assert update.status_code == 200

    client.post(
        "/api/users",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "alicepass",
            "is_admin": False,
        },
        auth=ADMIN_AUTH,
    )

    created = client.post(
        "/api/links",
        json={
            "target_url": "https://example.com/alice",
            "code": "alice-legacy",
            "domain": "tkgo.de",
        },
        auth=("alice", "alicepass"),
    )
    assert created.status_code == 201

    restrict = client.put(
        "/api/settings",
        data={
            "managed_domains": "911777.xyz tkgo.de*",
            "short_code_length": str(original["short_code_length"]),
            "short_link_path": original["short_link_path"],
            "logo_url": original["logo_url"],
            "icon_url": original["icon_url"],
        },
        auth=ADMIN_AUTH,
    )
    assert restrict.status_code == 200

    login = client.post(
        "/admin/login",
        data={"username": "alice", "password": "alicepass"},
    )
    assert login.status_code == 200

    dashboard = client.get("/admin?tab=links")
    assert dashboard.status_code == 200
    assert "tkgo.de/alice-legacy" in dashboard.text

    client.get("/admin/logout", follow_redirects=False)
    reset = client.put("/api/settings", json=original, auth=ADMIN_AUTH)
    assert reset.status_code == 200


def test_short_link_precedence_over_subdomain_redirect(
    client: "SimpleClient",
) -> None:
    redirect_response = client.post(
        "/api/subdomains",
        json={
            "host": "yet.la",
            "target_url": "https://portal.example.com/admin",
            "code": 302,
        },
        auth=ADMIN_AUTH,
    )
    assert redirect_response.status_code == 201

    client.post(
        "/api/links",
        json={"target_url": "https://example.com/home", "code": "portal"},
        auth=ADMIN_AUTH,
    )

    short_redirect = client.get(
        "/portal",
        headers={"host": "yet.la"},
        follow_redirects=False,
    )
    assert short_redirect.status_code == 302
    assert short_redirect.headers["location"] == "https://example.com/home"

    homepage = client.get("/", headers={"host": "yet.la"}, follow_redirects=False)
    assert homepage.status_code == 302
    assert homepage.headers["location"].startswith("https://portal.example.com/admin")


def test_non_admin_cannot_modify_other_users_links(client: "SimpleClient") -> None:
    admin_link = client.post(
        "/api/links",
        json={"target_url": "https://example.com/secret", "code": "secret"},
        auth=ADMIN_AUTH,
    ).json()

    client.post(
        "/api/users",
        json={
            "username": "bob",
            "email": "bob@example.com",
            "password": "bobpass",
            "is_admin": False,
        },
        auth=ADMIN_AUTH,
    )

    normal_auth = ("bob", "bobpass")

    forbidden_delete = client.delete(
        f"/api/links/{admin_link['id']}",
        auth=normal_auth,
    )
    assert forbidden_delete.status_code == 403
    assert forbidden_delete.json()["detail"] == "无权操作该短链"

    forbidden_update = client.put(
        f"/api/links/{admin_link['id']}",
        json={"code": "changed", "target_url": "https://example.com/new"},
        auth=normal_auth,
    )
    assert forbidden_update.status_code == 403
    assert forbidden_update.json()["detail"] == "无权操作该短链"
