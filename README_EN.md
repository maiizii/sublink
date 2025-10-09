# SubLink Short Link & Subdomain Platform

English | [简体中文](README.md)

SubLink powers short links and subdomain redirects for yet.la and similar multi-domain setups. The stack combines an HTTPS reverse proxy with an HTMX-enabled FastAPI admin so teams can manage routes under HTTP Basic authentication. Cloudflare terminates TLS, while Nginx proxies public traffic to the backend service.

> Current version: **v1.10.9.2** — The installer prints a version banner with a looping maintenance menu, and root-domain requests now redirect to `/admin` for faster access.

## Contents

- [Highlights](#highlights)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [TLS certificates & Nginx](#tls-certificates--nginx)
- [Common commands](#common-commands)
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

### One-click install

Designed for fresh Ubuntu 20.04/22.04 hosts. The Raw URL must include the `main` branch segment when fetching from `raw.githubusercontent.com`.

```bash
bash <(curl -Ls "https://raw.githubusercontent.com/maiizii/sublink/main/install.sh")
```

The installer will:

1. Ensure `curl`, `git`, `docker`, and the `docker compose` plugin are available;
2. Clone or refresh the repository at `/opt/sublink` (override with `SUBLINK_HOME`) and stay aligned with the target branch;
3. Prompt for `BASE_DOMAIN`, `CF_DNS_API_TOKEN`, `ACME_ACCOUNT_EMAIL`, and admin credentials while trimming Cloudflare tokens to avoid stray newlines;
4. Run `docker compose up -d --build`, register the `sublink.service` unit, and print the admin endpoint plus handy commands.

Running the script again displays a looping maintenance menu:

```
1 Update code and redeploy
2 Redeploy only (skip code update)
3 Stop services
4 Start services
5 Restart services
6 Show status
7 Request TLS certificates
8 Uninstall SubLink
0 Exit
```

Each choice returns to the prompt so you can chain multiple operations.

### Manual deployment

Prefer a fully manual rollout? Follow these steps:

1. Refresh packages and install Git:
   ```bash
   sudo apt-get update
   sudo apt-get install -y git
   ```
2. Clone the repository and enter the project directory:
   ```bash
   git clone https://github.com/maiizii/sublink.git
   cd sublink
   ```
3. Install Docker and the Compose plugin (run `sudo ./scripts/setup-ubuntu.sh` or replicate its commands) and add your user to the `docker` group:
   ```bash
   sudo ./scripts/setup-ubuntu.sh
   newgrp docker
   ```
4. Prepare configuration and data directories:
   ```bash
   cp .env.example .env
   vi .env   # Update BASE_DOMAIN, CF_DNS_API_TOKEN, ACME_ACCOUNT_EMAIL, etc.
   mkdir -p data
   chmod 700 data
   ```
5. Build and start the stack:
   ```bash
   docker compose up -d --build
   ```
6. Verify services and health checks:
   ```bash
   docker compose ps
   curl -sk https://<your-domain>/healthz
   ```

Sign in at `https://<your-domain>/admin` with the default `admin/admin` credentials. Visiting the bare primary domain (for example `https://yet.la`) now redirects to `/admin`, making the dashboard easy to find. Settings changes are stored in SQLite, so you rarely need to revisit `.env` after the first launch.

## TLS certificates & Nginx

Docker Compose starts an extra `cert_automation` service that manages certificate issuance end to end:

1. Populate `.env` with `BASE_DOMAIN` (space- or comma-separated) and `CF_DNS_API_TOKEN`. Add `ACME_ACCOUNT_EMAIL` only if you want renewal reminders. Optional knobs include `ACME_DIRECTORY`, `CERTBOT_RENEW_BEFORE_EXPIRY_DAYS`, `CF_DNS_PROPAGATION_SECONDS`, and `CERTBOT_ADDITIONAL_DOMAINS`.
2. The service first consumes the values from `.env` and, once the database is ready, mirrors updates from the admin **Settings → Managed domains** list. Any change triggers a forced issuance so the certificate always matches the latest domains.
3. Certificates and keys are written to the shared volume at `/etc/nginx/ssl/fullchain.cer` and `/etc/nginx/ssl/private.key`. The Nginx entrypoint waits for the files to appear before completing startup.
4. `infra/nginx/docker-entrypoint.d/50-auto-reload.sh` watches the directory with `inotifywait` and runs `nginx -s reload` after each renewal—no manual restart required.
5. For troubleshooting, run `docker compose logs cert_automation` to inspect ACME responses and Cloudflare DNS propagation.
6. `CERTBOT_RENEW_BEFORE_EXPIRY_DAYS` (default `15`) controls how many days before expiration automatic renewals kick in. Restart the `cert_automation` service after changing it.

> The management script's "Request TLS certificates" menu item only issues certificates for domains that are currently missing coverage; existing certificates continue to renew automatically inside the `cert_automation` service.

> See [docs/TLS_CERT_AUTOMATION.md](docs/TLS_CERT_AUTOMATION.md) for advanced usage and configuration notes.

## Common commands

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
