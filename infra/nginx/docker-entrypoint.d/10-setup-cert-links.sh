#!/bin/sh
set -eu

TARGET_ROOT="${SSL_TARGET_DIR:-/etc/nginx/ssl}"
SOURCE_ROOT="${SSL_SOURCE_DIR:-$TARGET_ROOT}"
FULLCHAIN="$TARGET_ROOT/fullchain.cer"
PRIVATE_KEY="$TARGET_ROOT/private.key"
WAIT_TIMEOUT="${SSL_BOOTSTRAP_TIMEOUT:-600}"
WAIT_INTERVAL="${SSL_BOOTSTRAP_INTERVAL:-5}"

ensure_target_dir() {
    if [ -d "$TARGET_ROOT" ]; then
        return
    fi

    if ! mkdir -p "$TARGET_ROOT" 2>/dev/null; then
        echo "[entrypoint] 无法创建证书目录: $TARGET_ROOT" >&2
        exit 1
    fi
}

find_cert_files() {
    directory="$1"

    if [ ! -d "$directory" ]; then
        return
    fi

    fullchain=""
    private=""

    for name in fullchain.cer fullchain.pem cert.pem certificate.pem; do
        candidate="$directory/$name"
        if [ -f "$candidate" ]; then
            fullchain="$candidate"
            break
        fi
    done

    for name in private.key privkey.pem privkey.key key.pem; do
        candidate="$directory/$name"
        if [ -f "$candidate" ]; then
            private="$candidate"
            break
        fi
    done

    if [ -n "$fullchain" ] && [ -n "$private" ]; then
        echo "$fullchain|$private"
    fi
}

link_certificates() {
    source_fullchain="$1"
    source_private="$2"

    if [ ! -w "$TARGET_ROOT" ]; then
        echo "[entrypoint] 证书目录不可写: $TARGET_ROOT" >&2
        echo "[entrypoint] 请确认挂载权限或卷设置" >&2
        exit 1
    fi

    ln -sf "$source_fullchain" "$FULLCHAIN"
    ln -sf "$source_private" "$PRIVATE_KEY"
    echo "[entrypoint] 已链接证书: $FULLCHAIN -> $source_fullchain" >&2
    echo "[entrypoint] 已链接私钥: $PRIVATE_KEY -> $source_private" >&2
    return 0
}

probe_sources() {
    candidate_pair="$(find_cert_files "$SOURCE_ROOT")"
    if [ -n "$candidate_pair" ]; then
        link_certificates "${candidate_pair%|*}" "${candidate_pair#*|}"
        return 0
    fi

    for candidate_dir in "$SOURCE_ROOT"/*; do
        candidate_pair="$(find_cert_files "$candidate_dir")"
        if [ -n "$candidate_pair" ]; then
            link_certificates "${candidate_pair%|*}" "${candidate_pair#*|}"
            return 0
        fi
    done

    return 1
}

ensure_target_dir

if [ -f "$FULLCHAIN" ] && [ -f "$PRIVATE_KEY" ]; then
    echo "[entrypoint] 证书文件已就绪: $TARGET_ROOT" >&2
    exit 0
fi

if [ ! -d "$SOURCE_ROOT" ]; then
    echo "[entrypoint] 证书源目录不存在: $SOURCE_ROOT" >&2
    exit 1
fi

elapsed=0
while [ "$elapsed" -le "$WAIT_TIMEOUT" ]; do
    if probe_sources; then
        exit 0
    fi

    if [ "$WAIT_TIMEOUT" -eq 0 ]; then
        break
    fi

    echo "[entrypoint] 未找到 TLS 证书，$WAIT_INTERVAL 秒后重试 (elapsed=${elapsed}s)" >&2
    sleep "$WAIT_INTERVAL"
    elapsed=$((elapsed + WAIT_INTERVAL))
done

echo "[entrypoint] 等待 $WAIT_TIMEOUT 秒后仍未找到 TLS 证书，请确认自动签发服务是否正常" >&2
exit 1
