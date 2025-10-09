#!/bin/sh
set -eu

TARGET_DIR="${CERT_TARGET_DIR:-/etc/nginx/ssl}"
LINEAGE="${RENEWED_LINEAGE:-}"

if [ -z "$LINEAGE" ] || [ ! -d "$LINEAGE" ]; then
    echo "[cert-automation] RENEWED_LINEAGE 未定义或目录不存在，跳过部署" >&2
    exit 0
fi

FULLCHAIN="$LINEAGE/fullchain.pem"
PRIVKEY="$LINEAGE/privkey.pem"

if [ ! -f "$FULLCHAIN" ] || [ ! -f "$PRIVKEY" ]; then
    echo "[cert-automation] 续签目录中缺少 fullchain/privkey，跳过部署" >&2
    exit 0
fi

mkdir -p "$TARGET_DIR"

# Ensure existing targets (including self-referencing symlinks) won't break copy
rm -f "$TARGET_DIR/fullchain.cer" "$TARGET_DIR/private.key"

cp "$FULLCHAIN" "$TARGET_DIR/fullchain.cer"
cp "$PRIVKEY" "$TARGET_DIR/private.key"
chmod 600 "$TARGET_DIR/private.key"

echo "[cert-automation] 已更新 $TARGET_DIR/fullchain.cer 与 private.key" >&2
