from __future__ import annotations

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


def test_create_short_link_invalid_code(client: "SimpleClient") -> None:
    response = client.post(
        "/api/links",
        json={"target_url": "https://example.com", "code": "-bad"},
        auth=ADMIN_AUTH,
    )
    assert response.status_code == 422
    detail = response.json().get("detail", [])
    assert any("短链编码" in item.get("msg", "") for item in detail)


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
            "site_domain": "yet.la",
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
            "site_domain": "https://www.example.com",
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


def test_root_request_returns_not_found(client: "SimpleClient") -> None:
    response = client.get("/", headers={"host": "yet.la"}, follow_redirects=False)
    assert response.status_code == 404
    assert response.text == "Not Found"


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
