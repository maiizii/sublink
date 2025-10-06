from backend.tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME


def test_settings_requires_admin(client: "SimpleClient") -> None:
    response = client.get("/api/settings")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"


def test_update_settings_affects_short_links(client: "SimpleClient") -> None:
    payload = {
        "site_domain": "https://Example.COM",
        "short_code_length": "4",
        "short_link_path": "r",
        "logo_url": "https://cdn.example.com/logo.png",
        "icon_url": "https://cdn.example.com/icon.png",
    }

    update = client.put(
        "/api/settings",
        data=payload,
        auth=(ADMIN_USERNAME, ADMIN_PASSWORD),
        follow_redirects=False,
    )
    assert update.status_code == 200
    body = update.json()
    assert body["site_domain"] == "example.com"
    assert body["short_code_length"] == 4
    assert body["short_link_path"] == "/r/"
    assert body["logo_url"] == payload["logo_url"]
    assert body["icon_url"] == payload["icon_url"]

    fetched = client.get("/api/settings", auth=(ADMIN_USERNAME, ADMIN_PASSWORD))
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["site_domain"] == "example.com"
    assert fetched_body["short_link_path"] == "/r/"

    create_response = client.post(
        "/api/links",
        data={"code": "jump", "target_url": "https://example.org"},
        auth=(ADMIN_USERNAME, ADMIN_PASSWORD),
    )
    assert create_response.status_code == 201

    redirect = client.get("/r/jump", headers={"host": "example.com"}, follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://example.org"

    missing = client.get("/jump", headers={"host": "example.com"}, follow_redirects=False)
    assert missing.status_code == 404
