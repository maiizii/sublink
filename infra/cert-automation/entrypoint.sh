#!/bin/sh
set -eu

CERT_NAME="${CERT_NAME:-sublink}"
ACME_ACCOUNT_EMAIL="${ACME_ACCOUNT_EMAIL:-}"
CF_DNS_API_TOKEN="${CF_DNS_API_TOKEN:-}"
ACME_DIRECTORY="${ACME_DIRECTORY:-https://acme-v02.api.letsencrypt.org/directory}"
CHECK_INTERVAL="${CERTBOT_CHECK_INTERVAL_SECONDS:-43200}"
PROPAGATION_WAIT="${CF_DNS_PROPAGATION_SECONDS:-60}"
DEPLOY_HOOK="/app/deploy-hook.sh"
DOMAINS_CACHE="/var/lib/cert-automation/current_domains"
CREDENTIALS_PATH="/etc/letsencrypt/cloudflare.ini"
STATE_DIR="$(dirname "$DOMAINS_CACHE")"

if [ -n "$ACME_ACCOUNT_EMAIL" ]; then
    CERTBOT_ACCOUNT_MODE="email"
else
    echo "[cert-automation] 未设置 ACME_ACCOUNT_EMAIL，将在无邮箱的情况下注册证书账户（请自行关注到期提醒）。" >&2
    CERTBOT_ACCOUNT_MODE="unsafe"
fi

if [ -z "$CF_DNS_API_TOKEN" ]; then
    echo "[cert-automation] CF_DNS_API_TOKEN 未设置，无法使用 Cloudflare DNS 验证" >&2
    exit 1
fi

case "$CHECK_INTERVAL" in
    ''|*[!0-9]*)
        echo "[cert-automation] CERTBOT_CHECK_INTERVAL_SECONDS 必须为数字秒数" >&2
        exit 1
        ;;
    *)
        :
        ;;
esac

mkdir -p "$STATE_DIR"

cat >"$CREDENTIALS_PATH" <<EOF_CREDS
# generated at container start
# see https://certbot-dns-cloudflare.readthedocs.io
 dns_cloudflare_api_token = $CF_DNS_API_TOKEN
EOF_CREDS
chmod 600 "$CREDENTIALS_PATH"

if [ -n "${ACME_EAB_KID:-}" ] && [ -n "${ACME_EAB_HMAC_KEY:-}" ]; then
    CERTBOT_EAB_OPTIONS="--eab-kid $ACME_EAB_KID --eab-hmac-key $ACME_EAB_HMAC_KEY"
else
    CERTBOT_EAB_OPTIONS=""
fi

while true; do
    if ! python3 /app/fetch_domains.py > /tmp/certbot.domains 2>/tmp/certbot.domains.log; then
        status=$?
        if [ "$status" = "10" ]; then
            echo "[cert-automation] 数据库暂未就绪，等待 10 秒后重试" >&2
            sleep 10
            continue
        fi
        if [ "$status" = "12" ]; then
            echo "[cert-automation] 尚未配置任何有效域名，等待 60 秒后重试" >&2
            cat /tmp/certbot.domains.log >&2 || true
            sleep 60
            continue
        fi
        echo "[cert-automation] 获取域名列表失败 (exit=$status)：" >&2
        cat /tmp/certbot.domains.log >&2 || true
        sleep 60
        continue
    fi

    if [ ! -s /tmp/certbot.domains ]; then
        echo "[cert-automation] 域名列表为空，60 秒后重试" >&2
        sleep 60
        continue
    fi

    mode="unchanged"
    if [ ! -d "/etc/letsencrypt/live/$CERT_NAME" ]; then
        mode="initial"
    elif [ ! -f "$DOMAINS_CACHE" ] || ! cmp -s /tmp/certbot.domains "$DOMAINS_CACHE"; then
        mode="changed"
    fi

    if [ "$mode" != "unchanged" ]; then
        echo "[cert-automation] 准备申请/更新证书 (mode=$mode)" >&2
        set -f
        set -- certbot certonly \
            --non-interactive \
            --agree-tos \
            --deploy-hook "$DEPLOY_HOOK" \
            --server "$ACME_DIRECTORY" \
            --dns-cloudflare \
            --dns-cloudflare-credentials "$CREDENTIALS_PATH" \
            --dns-cloudflare-propagation-seconds "$PROPAGATION_WAIT" \
            --cert-name "$CERT_NAME"

        if [ "$CERTBOT_ACCOUNT_MODE" = "email" ]; then
            set -- "$@" --email "$ACME_ACCOUNT_EMAIL" --no-eff-email
        else
            set -- "$@" --register-unsafely-without-email
        fi

        if [ -n "$CERTBOT_EAB_OPTIONS" ]; then
            # shellcheck disable=SC2086
            set -- "$@" $CERTBOT_EAB_OPTIONS
        fi

        if [ "$mode" = "changed" ]; then
            set -- "$@" --force-renewal
        fi

        while IFS= read -r domain; do
            [ -z "$domain" ] && continue
            set -- "$@" -d "$domain"
            case "$domain" in
                \*.*) ;;
                *) set -- "$@" -d "*.$domain" ;;
            esac
        done </tmp/certbot.domains

        if "$@"; then
            mv /tmp/certbot.domains "$DOMAINS_CACHE"
            echo "[cert-automation] 证书已成功签发/更新" >&2
            set +f
        else
            echo "[cert-automation] 证书申请失败" >&2
            set +f
            sleep 60
            continue
        fi
    else
        if ! certbot renew \
            --non-interactive \
            --deploy-hook "$DEPLOY_HOOK" \
            --dns-cloudflare \
            --dns-cloudflare-credentials "$CREDENTIALS_PATH" \
            --dns-cloudflare-propagation-seconds "$PROPAGATION_WAIT" \
            --no-random-sleep-on-renew \
            --cert-name "$CERT_NAME" \
            --keep-until-expiring >/tmp/certbot.renew.log 2>&1; then
            cat /tmp/certbot.renew.log >&2
        fi
    fi

    sleep "$CHECK_INTERVAL"
done
