#!/usr/bin/env bash
# 示例备份脚本：供 cron 调度使用，将 SubLink（yet.la）数据与日志归档后上传到远端存储。
# 根据生产环境修改 STORAGE_CMD 以适配 rsync、rclone 或云厂商 CLI。

set -euo pipefail

SUBLINK_ROOT="/opt/sublink"
BACKUP_ROOT="/var/backups/sublink"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE_PATH="$BACKUP_ROOT/sublink-${TIMESTAMP}.tar.gz"
RETENTION_DAYS=7

mkdir -p "$BACKUP_ROOT"

# 打包数据卷与应用日志，可按需扩展包含更多目录。
tar -czf "$ARCHIVE_PATH" \
  -C "$SUBLINK_ROOT" data \
  -C "$SUBLINK_ROOT" logs || { rm -f "$ARCHIVE_PATH"; exit 1; }

# 将归档同步到远端目标（示例：挂载的对象存储或备份服务器）。
STORAGE_CMD=(rsync -av "$ARCHIVE_PATH" backup@example.com:/srv/backups/sublink/)
"${STORAGE_CMD[@]}"

# 删除过期备份，保留最近 RETENTION_DAYS 天。
find "$BACKUP_ROOT" -name 'sublink-*.tar.gz' -mtime +$((RETENTION_DAYS - 1)) -delete
