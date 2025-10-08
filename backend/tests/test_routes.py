from __future__ import annotations

ADMIN_AUTH = ("admin", "admin")


def test_routes_endpoint_lists_subdomains(client: "SimpleClient") -> None:
    client.post(
        "/api/subdomains",
        json={"host": "alpha.test", "target_url": "https://example.com/a"},
        auth=ADMIN_AUTH,
    )
    client.post(
        "/api/subdomains",
        json={"host": "beta.test", "target_url": "https://example.com/b"},
        auth=ADMIN_AUTH,
    )

    response = client.get("/routes")
    assert response.status_code == 200
    hosts = [item["host"] for item in response.json()]
    assert hosts == ["alpha.test", "beta.test"]


def test_fallback_redirect_strips_site_domain_path(client: "SimpleClient") -> None:
    settings = client.get("/api/settings", auth=ADMIN_AUTH).json()
    settings["site_domain"] = "https://yet.la/admin"
    client.put("/api/settings", json=settings, auth=ADMIN_AUTH)

    response = client.get("/foo/bar", headers={"host": "yet.la"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://yet.la"


def test_fallback_redirect_uses_request_host_for_short_links(
    client: "SimpleClient",
) -> None:
    settings = client.get("/api/settings", auth=ADMIN_AUTH).json()
    settings["site_domain"] = "https://www.example.com"
    client.put("/api/settings", json=settings, auth=ADMIN_AUTH)

    response = client.get("/missing", headers={"host": "example.com"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://www.example.com"


def test_missing_short_link_with_nested_path_redirects_to_root(
    client: "SimpleClient",
) -> None:
    settings = client.get("/api/settings", auth=ADMIN_AUTH).json()
    settings["site_domain"] = "https://yet.la"
    client.put("/api/settings", json=settings, auth=ADMIN_AUTH)

    response = client.get(
        "/missing/nested",
        headers={"host": "yet.la"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "https://yet.la"
