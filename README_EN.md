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
- **Certificate automation**: `infra/cert-automation` watches the managed domains and requests TLS certificates via Cloudflare DNS-01, writing them to `/etc/nginx/ssl` and triggering live reloads.

## Prerequisites

1. **DNS records**: Configure the primary domain (e.g. `yet.la`) and wildcard (`*.yet.la`) at your DNS provider such as Cloudflare.
2. **Server environment**: Linux host (Ubuntu 22.04 LTS recommended) with root/sudo access.
3. **Tooling**: `git`, `docker`, the `docker compose` plugin, and `make` for helper commands.
4. **Cloudflare API token (optional ACME email)**: Create an API token with `Zone.DNS` edit permissions in Cloudflare. Add an email address only if you want renewal notices from the ACME provider.

## Quick start

```bash
# Fully automated install (recommended)
bash <(curl -Ls "https://raw.githubusercontent.com/maiizii/sublink/main/install.sh")

# Manual deployment (requires Docker & docker compose ahead of time)
git clone git@github.com:your-org/sublink.git
cd sublink
cp .env.example .env && vi .env
docker compose up -d --build
```

> Curious about what the automation covers? Check [one-click deployment script](#one-click-deployment-script) for a step-by-step breakdown and management options.

Nginx listens on `80/443`, redirects HTTP to HTTPS, and proxies requests to `backend:8000`.

Sign in at `https://<your-domain>/admin` using the default `admin/admin` credentials, then open **Settings** to update domains, link rules, and brand assets. All changes persist to the SQLite database—no `.env` management required.

## One-click deployment script

On a fresh Ubuntu 20.04/22.04 host you can simply run:

```bash
bash <(curl -Ls "https://raw.githubusercontent.com/maiizii/sublink/main/install.sh")
```

The script guides newcomers through every step on screen:

1. **System check** – requires root/sudo privileges, verifies `apt`, `docker`, and `docker compose`, and installs any missing components before starting the Docker daemon.
2. **Repository sync** – clones the project into `/opt/sublink` by default (override with `SUBLINK_HOME`) and keeps it aligned with the `main` branch.
3. **Interactive prompts** – collects:
   - `BASE_DOMAIN` (mandatory, accepts multiple entries separated by spaces or commas);
   - `CF_DNS_API_TOKEN` (mandatory, hidden input);
   - `ACME_ACCOUNT_EMAIL` (optional, press Enter to skip);
   - Admin username/password (press Enter to accept `admin` / `changeme`).
4. **Automated rollout** – prepares the data directory, runs `docker compose pull` + `up -d --build`, registers a `sublink.service` systemd unit, and prints the admin URL plus handy commands.

Re-running the same command detects existing installations and shows a management menu:

```
1) Update code and redeploy
2) Redeploy only (skip git update)
3) Stop services
4) Start services
5) Show status
6) Uninstall completely
```

- Option `1` performs a full `git pull`, refreshes `.env`, and restarts the stack.
- Option `2` keeps the current code and simply reapplies your latest configuration.
- Options `3/4/5` control or inspect the running services.
- Option `6` shuts everything down, removes the systemd unit, and deletes `/opt/sublink` (confirmation required).

> **Heads-up**
>
> - The installer targets Ubuntu 20.04/22.04 with `apt` and systemd; adapt it before using other distributions.
> - Customise the target directory or branch like so: `SUBLINK_HOME=/data/sublink SUBLINK_BRANCH=release bash <(curl -Ls ...)`.
> - Edit `/opt/sublink/.env` at any time and rerun the script with option `2` to roll the new settings into the containers.

## TLS certificates & Nginx

Docker Compose starts an extra `cert_automation` service that manages certificate issuance end to end:

1. Populate `.env` with `BASE_DOMAIN` (space- or comma-separated) and `CF_DNS_API_TOKEN`. Add `ACME_ACCOUNT_EMAIL` only if you want renewal reminders. Optional knobs include `ACME_DIRECTORY`, `CF_DNS_PROPAGATION_SECONDS`, and `CERTBOT_ADDITIONAL_DOMAINS`.
2. The service first consumes the values from `.env` and, once the database is ready, mirrors updates from the admin **Settings → Managed domains** list. Any change triggers a forced issuance so the certificate always matches the latest domains.
3. Certificates and keys are written to the shared volume at `/etc/nginx/ssl/fullchain.cer` and `/etc/nginx/ssl/private.key`. The Nginx entrypoint waits for the files to appear before completing startup.
4. `infra/nginx/docker-entrypoint.d/50-auto-reload.sh` watches the directory with `inotifywait` and runs `nginx -s reload` after each renewal—no manual restart required.
5. For troubleshooting, run `docker compose logs cert_automation` to inspect ACME responses and Cloudflare DNS propagation.

> See [docs/TLS_CERT_AUTOMATION.md](docs/TLS_CERT_AUTOMATION.md) for advanced usage and configuration notes.

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
- [TLS automation guide](docs/TLS_CERT_AUTOMATION.md)

For issues or feature ideas, open a ticket or reach out to the maintainers.
