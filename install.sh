#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/maiizii/sublink.git"
INSTALL_DIR="${SUBLINK_HOME:-/opt/sublink}"
BRANCH="${SUBLINK_BRANCH:-main}"
SYSTEMD_SERVICE="sublink.service"
APT_UPDATED=false

log() {
  local level="$1"; shift
  printf '[%s] %s\n' "$level" "$*"
}

log_step() { log "步骤" "$*"; }
log_info() { log "信息" "$*"; }
log_warn() { log "警告" "$*" >&2; }
log_error() { log "错误" "$*" >&2; }

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    log_error "请使用 root 或 sudo 权限运行：sudo bash install.sh"
    exit 1
  fi
}

cleanup_docker_repo() {
  local docker_list="/etc/apt/sources.list.d/docker.list"
  if [[ -f "$docker_list" ]]; then
    if ! grep -Eq '^deb \\[arch=[^ ]+ signed-by=/etc/apt/keyrings/docker.gpg\\] https://download.docker.com/linux/ubuntu [^ ]+ stable$' "$docker_list" 2>/dev/null; then
      log_warn "检测到损坏的 Docker 软件源配置，已移除以便重新生成"
      rm -f "$docker_list"
    fi
  fi
}

ensure_apt_update() {
  if [[ "$APT_UPDATED" == false ]]; then
    cleanup_docker_repo
    log_step "更新系统软件源"
    apt-get update
    APT_UPDATED=true
  fi
}

ensure_packages() {
  ensure_apt_update
  log_step "安装基础依赖 (curl git ca-certificates gnupg lsb-release python3)"
  apt-get install -y curl git ca-certificates gnupg lsb-release python3
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    log_info "检测到 Docker 已安装：$(docker --version)"
    return
  fi
  ensure_packages
  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
    log_step "导入 Docker GPG 公钥"
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  fi
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  log_step "写入 Docker 软件源配置"
  local repo_entry
  repo_entry="deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable"
  printf '%s\n' "$repo_entry" | tee /etc/apt/sources.list.d/docker.list >/dev/null

  log_step "刷新 Docker 软件源"
  apt-get update
  log_step "安装 Docker 引擎与 Compose 插件"
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  if systemctl is-active --quiet docker; then
    log_info "Docker 服务已启动"
  else
    log_warn "Docker 服务未正常启动，请执行 systemctl status docker 排查"
  fi
  if [[ -n "${SUDO_USER:-}" ]]; then
    usermod -aG docker "${SUDO_USER}"
    log_info "已将 ${SUDO_USER} 加入 docker 用户组，重新登录生效"
  fi
}

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_BIN=(docker compose)
    COMPOSE_DESC="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN=(docker-compose)
    COMPOSE_DESC="docker-compose"
  else
    log_error "未检测到 docker compose，请确认 Docker 已正确安装"
    exit 1
  fi
  log_info "使用 Compose 命令：$COMPOSE_DESC"
}

ensure_repo() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    return
  fi
  log_step "克隆 SubLink 仓库到 $INSTALL_DIR"
  mkdir -p "$INSTALL_DIR"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
}

update_repo() {
  log_step "拉取最新代码"
  git -C "$INSTALL_DIR" fetch --all --prune
  git -C "$INSTALL_DIR" reset --hard "origin/${BRANCH}"
  git -C "$INSTALL_DIR" submodule update --init --recursive
}

copy_env_example() {
  local env_file="$INSTALL_DIR/.env"
  if [[ ! -f "$env_file" ]]; then
    cp "$INSTALL_DIR/.env.example" "$env_file"
    log_info "已根据 .env.example 初始化配置文件"
  fi
}

read_env() {
  local key="$1" env_file="$INSTALL_DIR/.env"
  if [[ -f "$env_file" ]]; then
    grep -E "^${key}=" "$env_file" | head -n1 | cut -d '=' -f2-
  fi
}

set_env() {
  local key="$1" value="$2" env_file="$INSTALL_DIR/.env"
  KEY="$key" VALUE="$value" FILE_PATH="$env_file" python3 - <<'PY'
import os
from pathlib import Path

key = os.environ["KEY"]
value = os.environ["VALUE"]
path = Path(os.environ["FILE_PATH"])
if not path.exists():
    lines = []
else:
    lines = path.read_text().splitlines()

updated = False
for idx, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[idx] = f"{key}={value}"
        updated = True
        break

if not updated:
    lines.append(f"{key}={value}")

text = "\n".join(lines)
if text and not text.endswith("\n"):
    text += "\n"
path.write_text(text)
PY
}

normalize_domains() {
  python3 - "$@" <<'PY'
import re, sys
raw = " ".join(sys.argv[1:])
parts = re.split(r"[\s,]+", raw.strip())
seen = []
for part in parts:
    if not part:
        continue
    host = part.lower()
    if host not in seen:
        seen.append(host)
if not seen:
    sys.exit(1)
print(" ".join(seen))
PY
}

prompt_required_domains() {
  local current
  current="$(read_env BASE_DOMAIN || true)"
  while true; do
    local prompt="请输入域名（多个以空格或逗号分隔）"
    if [[ -n "$current" ]]; then
      prompt+=" [当前: $current]"
    fi
    prompt+="："
    read -r -p "$prompt" input || true
    if [[ -z "$input" ]]; then
      if [[ -n "$current" ]]; then
        log_info "保留原有域名：$current"
        echo "$current"
        return
      fi
      log_warn "域名不能为空"
      continue
    fi
    if normalized="$(normalize_domains "$input" 2>/dev/null)"; then
      log_info "域名已归一化：$normalized"
      echo "$normalized"
      return
    fi
    log_warn "未检测到有效域名，请重新输入"
  done
}

prompt_secret() {
  local key="$1" message="$2"
  local current
  current="$(read_env "$key" || true)"
  local hint="未设置"
  if [[ -n "$current" ]]; then
    hint="已配置"
  fi
  while true; do
    read -rsp "$message (当前：$hint)：" input || true
    echo
    if [[ -z "$input" ]]; then
      if [[ -n "$current" ]]; then
        log_info "保留已有 $key"
        echo "$current"
        return
      fi
      log_warn "$key 不能为空"
      continue
    fi
    echo "$input"
    return
  done
}

prompt_optional() {
  local key="$1" message="$2"
  local current
  current="$(read_env "$key" || true)"
  read -r -p "$message" input || true
  if [[ -z "$input" ]]; then
    if [[ -n "$current" ]]; then
      log_info "保留已有 $key=$current"
      echo "$current"
    else
      echo ""
    fi
  else
    echo "$input"
  fi
}

prompt_with_default() {
  local key="$1" message="$2" default="$3"
  local current
  current="$(read_env "$key" || true)"
  local effective_default="$default"
  if [[ -n "$current" ]]; then
    effective_default="$current"
  fi
  read -r -p "$message" input || true
  if [[ -z "$input" ]]; then
    echo "$effective_default"
  else
    echo "$input"
  fi
}

prepare_env() {
  copy_env_example
  local domains token email admin_user admin_pass
  domains="$(prompt_required_domains)"
  token="$(prompt_secret CF_DNS_API_TOKEN "请输入 Cloudflare CF_DNS_API_TOKEN")"
  email="$(prompt_optional ACME_ACCOUNT_EMAIL "请输入 ACME 通知邮箱（可选，直接回车跳过）：")"
  admin_user="$(prompt_with_default ADMIN_USER "请输入管理员账号（默认 admin）：" "admin")"
  admin_pass="$(prompt_with_default ADMIN_PASS "请输入管理员密码（默认 changeme）：" "changeme")"
  set_env BASE_DOMAIN "$domains"
  set_env CF_DNS_API_TOKEN "$token"
  set_env ACME_ACCOUNT_EMAIL "$email"
  set_env ADMIN_USER "$admin_user"
  set_env ADMIN_PASS "$admin_pass"
  install -d -m 700 "$INSTALL_DIR/data"
  log_info "数据目录已准备：$INSTALL_DIR/data (700)"
}

install_systemd_unit() {
  local compose_exec compose_args
  if [[ "${COMPOSE_BIN[*]}" == "docker compose" ]]; then
    compose_exec="$(command -v docker)"
    compose_args="compose"
    cat <<UNIT >/etc/systemd/system/${SYSTEMD_SERVICE}
[Unit]
Description=SubLink Stack
Requires=docker.service
After=network-online.target docker.service

[Service]
Type=oneshot
WorkingDirectory=${INSTALL_DIR}
ExecStart=${compose_exec} ${compose_args} up -d
ExecStop=${compose_exec} ${compose_args} down
RemainAfterExit=yes
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT
  else
    compose_exec="$(command -v docker-compose)"
    cat <<UNIT >/etc/systemd/system/${SYSTEMD_SERVICE}
[Unit]
Description=SubLink Stack
Requires=docker.service
After=network-online.target docker.service

[Service]
Type=oneshot
WorkingDirectory=${INSTALL_DIR}
ExecStart=${compose_exec} up -d
ExecStop=${compose_exec} down
RemainAfterExit=yes
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT
  fi
  systemctl daemon-reload
  systemctl enable --now "$SYSTEMD_SERVICE"
  log_info "已启用 systemd 服务：$SYSTEMD_SERVICE"
}

deploy_stack() {
  detect_compose
  log_step "拉取容器镜像"
  if ! "${COMPOSE_BIN[@]}" -f "$INSTALL_DIR/docker-compose.yml" pull; then
    log_warn "拉取镜像失败，可能因网络限制，将继续使用本地构建"
  fi
  log_step "构建并启动服务"
  "${COMPOSE_BIN[@]}" -f "$INSTALL_DIR/docker-compose.yml" up -d --build
  install_systemd_unit
  log_step "当前运行状态"
  "${COMPOSE_BIN[@]}" -f "$INSTALL_DIR/docker-compose.yml" ps
  local primary_domain
  primary_domain="$(read_env BASE_DOMAIN | awk '{print $1}')"
  cat <<INFO
[完成] SubLink 已部署完成。
- 后台入口：https://${primary_domain:-<你的域名>}/admin
- 默认账号：$(read_env ADMIN_USER) / $(read_env ADMIN_PASS)
- 查看日志：cd $INSTALL_DIR && ${COMPOSE_DESC} logs -f
INFO
}

stop_stack() {
  detect_compose
  "${COMPOSE_BIN[@]}" -f "$INSTALL_DIR/docker-compose.yml" down
  log_info "服务已停止"
}

start_stack() {
  detect_compose
  "${COMPOSE_BIN[@]}" -f "$INSTALL_DIR/docker-compose.yml" up -d
  log_info "服务已启动"
}

show_status() {
  detect_compose
  "${COMPOSE_BIN[@]}" -f "$INSTALL_DIR/docker-compose.yml" ps
}

uninstall_stack() {
  detect_compose
  if [[ -f /etc/systemd/system/${SYSTEMD_SERVICE} ]]; then
    systemctl disable --now "$SYSTEMD_SERVICE" || true
    rm -f "/etc/systemd/system/${SYSTEMD_SERVICE}"
    systemctl daemon-reload
    log_info "已移除 systemd 服务"
  fi
  "${COMPOSE_BIN[@]}" -f "$INSTALL_DIR/docker-compose.yml" down -v || true
  rm -rf "$INSTALL_DIR"
  log_info "SubLink 已卸载"
}

menu() {
  cat <<MENU
检测到已安装的 SubLink 环境（目录：$INSTALL_DIR）。
请选择操作：
  1) 更新代码并重新部署
  2) 仅重新部署（不更新代码）
  3) 停止服务
  4) 启动服务
  5) 查看运行状态
  6) 完全卸载
MENU
  read -r -p "请输入选项 [1-6]：" choice || true
  case "$choice" in
    1)
      ensure_packages
      install_docker
      ensure_repo
      update_repo
      prepare_env
      deploy_stack
      ;;
    2)
      ensure_packages
      install_docker
      ensure_repo
      prepare_env
      deploy_stack
      ;;
    3)
      stop_stack
      ;;
    4)
      start_stack
      ;;
    5)
      show_status
      ;;
    6)
      read -r -p "确认要卸载并删除所有数据？(yes/NO)：" confirm || true
      if [[ "$confirm" == "yes" ]]; then
        uninstall_stack
      else
        log_warn "已取消卸载"
      fi
      ;;
    *)
      log_warn "无效选项"
      ;;
  esac
}

initial_install() {
  ensure_packages
  install_docker
  ensure_repo
  copy_env_example
  prepare_env
  deploy_stack
}

main() {
  require_root
  if [[ ! -f /etc/os-release ]]; then
    log_error "无法识别当前系统，请使用 Ubuntu 20.04/22.04 并确保存在 /etc/os-release"
    exit 1
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    log_error "未检测到 apt-get，本脚本当前仅支持 Ubuntu/Debian 系列发行版"
    exit 1
  fi
  export DEBIAN_FRONTEND=noninteractive
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    menu
  else
    initial_install
  fi
}

main "$@"
