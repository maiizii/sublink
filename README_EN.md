# SubLink Short Link & Subdomain Platform

English | [简体中文](README.md)

SubLink powers short links and subdomain redirects for yet.la and similar multi-domain setups. The stack combines an HTTPS reverse proxy with an HTMX-enabled FastAPI admin so teams can manage routes under HTTP Basic authentication. Cloudflare terminates TLS, while Nginx proxies public traffic to the backend service.

> Current version: **v1.10.9** — The admin dashboard now ships with Simplified Chinese and English translations, and the documentation set has matching bilingual coverage.

## Contents

- [Highlights](#highlights)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [One-command helpers](#one-command-helpers)
- [Smoke testing](#smoke-testing)
- [Further reading](#further-reading)

## Highlights

- **Unified reverse proxy**: `infra/nginx/conf.d/sublink.upstream.conf` listens on `80/443`, enforces HTTPS, and forwards to the FastAPI backend.
- **Authenticated admin & API**: `backend/app/main.py` exposes an HTMX dashboard plus REST endpoints. Mutations require HTTP Basic or the built-in login form.
- **Role-based access**: `backend/app/models.py` defines the `users` table with administrator and standard roles for CRUD and password rotation.
- **Subdomain guardrails**: `backend/app/subdomain_service.py` seeds reserved prefixes and surfaces `/api/subdomain-blacklist` for edits.
- **Multi-domain control**: `backend/app/settings_service.py` persists `managed_domains`, normalises hostnames, and generates default `www.` mappings.
- **Bilingual interface**: `backend/app/i18n/` contains Simplified Chinese and English strings. Users can switch languages from the top-right toggle in the dashboard.
- **Deployment scripts**: `docker-compose*.yml` and `infra/nginx/docker-entrypoint.d/` automate container orchestration and certificate checks.

## Prerequisites

1. **DNS records**: Configure the primary domain (e.g. `yet.la`) and wildcard (`*.yet.la`) at your DNS provider such as Cloudflare.
2. **Server environment**: Linux host (Ubuntu 22.04 LTS recommended) with root/sudo access.
3. **Tooling**: `git`, `docker`, the `docker compose` plugin, and `make` for helper commands.
4. **TLS material**: Provide certificates covering the root and wildcard domains.

## Quick start

```bash
# 1. Clone the repository
$ git clone git@github.com:your-org/sublink.git
$ cd sublink

# 2. Launch the stack (rebuild images on first run)
$ docker compose up -d --build
```

Nginx listens on `80/443`, redirects HTTP to HTTPS, and proxies requests to `backend:8000`.

Sign in at `https://<your-domain>/admin` using the default `admin/admin` credentials, then open **Settings** to update domains, link rules, and brand assets. All changes persist to the SQLite database—no `.env` management required.

## One-command helpers

The root `Makefile` wraps common Docker Compose tasks:

```bash
make up      # build and start services in the background
make down    # stop and clean up containers, networks, and anonymous volumes
make logs    # tail all service logs
make test    # run Pytest inside the backend container
make shell   # open an interactive shell inside the backend container
```

## Smoke testing

Use `scripts/smoke.sh` for end-to-end regression checks:

- Create a short link and confirm `/{code}` returns `302` with the correct `Location` header.
- Create a subdomain redirect and verify 3xx responses using a custom `Host` header.
- Clean up all temporary entries after the test run.

Adjust the following environment variables if needed:

| Variable | Default | Description |
| --- | --- | --- |
| `BASE_URL` | `https://yet.la` | FastAPI service endpoint |
| `ADMIN_USER` / `ADMIN_PASS` | `admin` / `admin` | HTTP Basic credentials |
| `SMOKE_SUBDOMAIN_CODE` | `302` | Status code used for the subdomain redirect |

Execute the script:

```bash
bash scripts/smoke.sh
```

## Further reading

- [NGINX subdomain routing design](docs/NGINX_SUBDOMAIN_ROUTING.md)
- [Team onboarding guide](docs/ONBOARDING.md)
- [Backup script example](docs/backup-example.sh)

For issues or feature ideas, open a ticket or reach out to the maintainers.
