#!/bin/sh
set -eu

TARGET_ROOT="${SSL_TARGET_DIR:-/etc/nginx/ssl}"

if ! command -v inotifywait >/dev/null 2>&1; then
    echo "[entrypoint] 未检测到 inotifywait，跳过证书热重载监控" >&2
    exit 0
fi

if [ ! -d "$TARGET_ROOT" ]; then
    echo "[entrypoint] 证书目录不存在，跳过自动重载: $TARGET_ROOT" >&2
    exit 0
fi

(
    while true; do
        inotifywait -e close_write,create,move "$TARGET_ROOT" >/dev/null 2>&1 || continue
        if [ -f "$TARGET_ROOT/fullchain.cer" ] && [ -f "$TARGET_ROOT/private.key" ]; then
            if nginx -s reload 2>/tmp/nginx-reload.log; then
                echo "[entrypoint] 检测到证书更新，已执行 nginx -s reload" >&2
            else
                echo "[entrypoint] 尝试重新加载 Nginx 失败:" >&2
                cat /tmp/nginx-reload.log >&2 || true
            fi
        fi
    done
) &
