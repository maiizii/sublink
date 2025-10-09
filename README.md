# SubLink 短链子域管理平台

简体中文 | [English](README_EN.md)

SubLink 是 yet.la 等多域名的自托管短链与子域跳转管理平台，提供受 HTTP Basic 保护的管理后台与 API，用于维护二级域路由与短链接。Cloudflare 负责 DNS 与 TLS
终止，Nginx 统一接受公网流量并转发到 FastAPI 后端。

> Open Source Short-Link & Domain Routing System

> 当前版本：**v1.10.9** —— 管理后台现已内置中英文切换，配套文档同步更新，方便全球团队协同维护短链与子域跳转。

## 界面预览

![管理后台登录页](https://image.dooo.ng/t/2025/10/09/68e73c26a3f4f.webp)

![管理后台仪表盘](https://image.dooo.ng/t/2025/10/09/68e73c26a3f34.webp)

![短链管理列表](https://image.dooo.ng/t/2025/10/09/68e73c26a7204.webp)

![子域路由配置](https://image.dooo.ng/t/2025/10/09/68e73c26a62bd.webp)

![站点设置页面](https://image.dooo.ng/t/2025/10/09/68e73c26a4837.webp)

## 目录

- [本仓库包含什么？](#本仓库包含什么)
- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [一键命令](#一键命令)
- [验收脚本](#验收脚本)
- [HTTPS 入口与冒烟验证](#https-入口与冒烟验证)
- [安装与部署指南](#安装与部署指南)
- [证书与 Nginx 配置](#证书与-nginx-配置)
- [Cloudflare 设置](#cloudflare-设置)
- [部署完成后的使用方式](#部署完成后的使用方式)
- [子域屏蔽名单与长度限制](#子域屏蔽名单与长度限制)
- [管理域名列表与短链域控制](#管理域名列表与短链域控制)
- [API 说明与示例 curl](#api-说明与示例-curl)
- [环境变量](#环境变量)
- [数据存储](#数据存储)
- [安全基线](#安全基线)
- [测试运行](#测试运行)
- [常见故障排障](#常见故障排障)

## 本仓库包含什么？

> ✅ SubLink 当前版本提供一套可直接部署的 HTTPS 反向代理 + FastAPI 管理后端，覆盖 yet.la 等域名的短链接与子域跳转管理需求。

```
.
├── apps/                  # 历史示例页面（默认部署不再挂载到 Nginx）
├── backend/               # FastAPI 服务，提供管理后台与 API
├── data/                  # SQLite 数据卷（容器启动时自动创建）
├── docs/                  # 设计文档与脚本示例
├── infra/nginx/           # Nginx 配置与入口脚本
├── docker-compose.yml     # 生产部署所用的 Compose 模板
├── docker-compose.override.yml
└── scripts/               # 自动化脚本（如备份、冒烟测试）
```

- **统一反向代理**：`infra/nginx/conf.d/sublink.upstream.conf` 监听 `80/443`，负责 HTTP→HTTPS 重定向与上游代理。
- **认证后台 + API**：`backend/app/main.py` 提供 HTMX 管理界面及 REST API，所有写操作需登录（支持 HTTP Basic 或后台表单）。
- **多用户权限管理**：`backend/app/models.py` 中新增 `users` 表，支持区分管理员与普通用户，并在后台界面完成用户 CRUD 与密码管理。
- **子域屏蔽名单管控**：`backend/app/subdomain_service.py` 会在启动时写入默认的保留前缀列表，并通过 `/api/subdomain-blacklist` 提供增删改查接口，管理员可自定义限制普通用户可用的子域。
- **多域名统一管理**：`backend/app/settings_service.py` 负责持久化 `managed_domains`，允许短链与访客跳转覆盖多个域名，并自动生成主域与 `www.` 映射。
- **多语言管理界面**：`backend/app/i18n/` 引入中英文翻译，登录后可一键切换界面语言，适配跨地区协作与多语种运营。
- **部署脚本**：`docker-compose*.yml` 与 `infra/nginx/docker-entrypoint.d/` 负责容器化部署与证书挂载自检。
- **证书自动化**：`infra/cert-automation` 容器读取数据库中的管理域名并调用 Cloudflare DNS-01 申请/续签 TLS 证书，自动写入 `/etc/nginx/ssl` 并触发入口脚本热重载。

更多背景信息请参阅 [docs/NGINX_SUBDOMAIN_ROUTING.md](docs/NGINX_SUBDOMAIN_ROUTING.md)。该文档结合最新的生产配置，说明了如何使用 Nginx 通过数据库驱动的规则完成泛域名跳转。

## 前置条件

1. **域名解析**：在 DNS 服务商（如 Cloudflare）为主域（例如 `yet.la`）与其泛域名（如 `*.yet.la`）配置 A/AAAA 记录指向服务器公网 IP。
2. **服务器环境**：Linux（推荐 Ubuntu 22.04 LTS），具备 root/sudo 权限。
3. **运行依赖**：`git`、`docker`、`docker compose` 插件、`make`（用于 Makefile 命令）。
4. **Cloudflare API Token（可选 ACME 邮箱）**：在 Cloudflare 控制台创建具备 `Zone.DNS` 编辑权限的 API Token。如需接收证书到期提醒，可额外准备一个邮箱用于 ACME 账号注册。

## 快速开始

```bash
# 全自动一键部署（推荐）
bash <(curl -Ls "https://raw.githubusercontent.com/maiizii/sublink/main/install.sh")

# 或手动部署（需先准备 Docker / docker compose）
git clone git@github.com:your-org/sublink.git
cd sublink
cp .env.example .env && vi .env
docker compose up -d --build
```

> 若希望在运行过程中查看可选参数、更新流程，请参考下方的 [一键部署脚本](#一键部署脚本) 章节。

Nginx 默认监听 `80/443`，HTTP 请求统一 301 跳转至 HTTPS 并转发至后端 `backend:8000`。

启动完成后，可使用默认管理员账号 `admin/admin` 登录 `https://<你的域名>/admin`，并在「设置」页更新基础域名、管理域名列表、短链默认长度、路径前缀以及 Logo/Icon。所有配置会持久化到数据库，后续无需维护额外的 `.env` 文件。

## 一键部署脚本

针对全新 Ubuntu 20.04/22.04 服务器，提供 `install.sh` 一键脚本，可直接在目标机器执行：

```bash
bash <(curl -Ls "https://raw.githubusercontent.com/maiizii/sublink/main/install.sh")
```

脚本会在屏幕上逐步提示输入，确保“小白”也能完成部署：

1. **系统自检**：要求 root/sudo 权限，自动检测 `apt`、`docker`、`docker compose`，缺少时会安装并启动 Docker 服务。
2. **仓库获取**：默认将项目克隆至 `/opt/sublink`（可通过环境变量 `SUBLINK_HOME` 自定义），并保持与 `main` 分支同步。
3. **参数填写**：逐项提示：
   - `BASE_DOMAIN`（必填，可输入多个域名，支持空格/逗号分隔）；
   - `CF_DNS_API_TOKEN`（必填，隐藏输入）；
   - `ACME_ACCOUNT_EMAIL`（可选，直接回车跳过）；
   - 管理员账号/密码（回车使用 `admin` / `changeme`）。
4. **自动部署**：创建数据目录、执行 `docker compose pull` + `up -d --build`、写入 systemd 服务（`sublink.service`），并展示后台入口与常见命令。

首次安装完成后，再次执行同一命令会检测到既有环境并给出操作菜单：

```
1) 更新代码并重新部署
2) 仅重新部署（不更新代码）
3) 停止服务
4) 启动服务
5) 查看运行状态
6) 完全卸载
```

- 选择 `1` 会 `git pull` 最新代码、重新收集参数并重启；
- 选择 `2` 会沿用当前代码，仅根据 `.env` 重启；
- `3/4/5` 用于常规停启、查看状态；
- `6` 将停掉容器、删除 systemd 服务及 `/opt/sublink` 目录（需输入 `yes` 确认）。

> **注意事项**
>
> - 脚本默认支持 Ubuntu 20.04/22.04，依赖 `apt` 与 systemd；其他发行版可参考脚本内容进行调整。
> - 如需自定义安装目录或分支，可在执行前设置变量：`SUBLINK_HOME=/data/sublink SUBLINK_BRANCH=release bash <(curl -Ls ... )`。
> - 完成安装后，可随时手动编辑 `/opt/sublink/.env`，然后重新运行脚本选择 `2` 即可应用新配置。

## 一键命令

项目根目录提供 `Makefile`，封装常用的 Compose 操作：

```bash
# 构建并以后台模式启动所有服务（等价于 docker compose up -d --build）
make up

# 停止并清理容器、网络与匿名卷
make down

# 持续追踪所有服务日志
make logs

# 在后端容器内运行 Pytest
make test

# 进入后端容器交互式 Shell
make shell
```

## 验收脚本

`scripts/smoke.sh` 可用于回归验证 FastAPI 接口：

- 创建短链并确认 `/{code}` 返回 302 与正确 `Location`；
- 创建子域跳转并使用自定义 `Host` 验证 3xx；
- 用完后自动清理。

运行前确保服务已启动并根据需要调整以下环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BASE_URL` | `https://yet.la` | FastAPI 服务地址（可改为本地 IP/域名） |
| `ADMIN_USER` / `ADMIN_PASS` | `admin` / `admin` | HTTP Basic 凭据 |
| `SMOKE_SUBDOMAIN_CODE` | `302` | 子域跳转使用的状态码 |

执行示例：

```bash
bash scripts/smoke.sh
```

如果只需快速确认 HTTPS 入口的 301 跳转与子域生效情况，可执行 `scripts/proxy-smoke.sh`，该脚本会模拟 Cloudflare → 源站 的完整握手流程并验证 Basic Auth、防未授权访问等关键逻辑。

## HTTPS 入口与冒烟验证

容器启动后 Nginx 会：

- 在 `80` 端口返回 301 → `https://$host$request_uri`；
- 在 `443` 端口加载 `/etc/nginx/ssl/{fullchain.cer,private.key}` 并反向代理到 `backend:8000`；
- 透传 `Authorization`、`Host` 以及标准的 `X-Forwarded-*` 头。

冒烟测试示例（需替换为实际域名/IP，并信任证书）：

```bash
# 1. HTTP 自动跳转 HTTPS
curl -I http://yet.la/

# 2. 健康检查
curl -sk https://yet.la/healthz

# 3. 未授权访问返回 401（包含 WWW-Authenticate）
curl -skI https://yet.la/api/subdomains

# 4. 携带 Basic Auth 创建子域（JSON）
curl -sk -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"host":"foo.yet.la","target_url":"https://example.com","code":302}' \
  https://yet.la/api/subdomains
```

## 安装与部署指南

以下步骤在一台全新 Ubuntu 22.04 VPS 上验证通过，可按需调整：

1. **更新软件源并安装 Git（如系统自带可跳过）**
   ```bash
   sudo apt-get update
   sudo apt-get install -y git
   ```
2. **克隆仓库并进入项目目录**
   ```bash
   git clone https://github.com/your-org/sublink.git
   cd sublink
   ```
3. **安装运行依赖（Docker、Docker Compose 插件）**
   - 推荐执行仓库脚本：
     ```bash
     sudo ./scripts/setup-ubuntu.sh
     ```
   - 若无法使用脚本，可参考脚本内容手动安装。
4. **刷新 Docker 用户组（如需）**
   ```bash
   newgrp docker
   ```
5. **准备配置与数据目录**
   ```bash
   cp .env.example .env
   vi .env   # 填写 BASE_DOMAIN、CF_DNS_API_TOKEN，如需提醒可填写 ACME_ACCOUNT_EMAIL
   mkdir -p data
   chmod 700 data
   ```
6. **启动服务**
   ```bash
   docker compose up -d --build
   ```
8. **验证容器状态与健康检查**
   ```bash
   docker compose ps
   curl -sk https://yet.la/healthz
   curl -sk https://yet.la/routes
   ```
9. **（可选）放行防火墙端口**
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

完成后，可通过 `https://yet.la/admin` 登录后台或使用 API 进行管理。

## 证书与 Nginx 配置

`docker-compose.yml` 默认会额外启动 `cert_automation` 服务，通过 Cloudflare DNS-01 自动申请并续签 TLS 证书：

1. 在 `.env` 中填写 `BASE_DOMAIN`（支持空格或逗号分隔多个域名）与 `CF_DNS_API_TOKEN`。如需接收到期提醒，可额外填写 `ACME_ACCOUNT_EMAIL`。若需覆盖默认 ACME 端点或追加域名，可设置 `ACME_DIRECTORY`、`CF_DNS_PROPAGATION_SECONDS`、`CERTBOT_ADDITIONAL_DOMAINS` 等变量。
2. `cert_automation` 会先读取 `.env` 中的域名，并在数据库初始化后同步后台「设置」页中的「管理域名」。一旦域名列表发生变化会强制重新签发证书，确保证书始终覆盖后台配置。
3. 证书与私钥被写入共享卷 `/etc/nginx/ssl/fullchain.cer` 与 `/etc/nginx/ssl/private.key`，`infra/nginx` 入口脚本会在容器启动时等待文件就绪并创建软链接。
4. `infra/nginx/docker-entrypoint.d/50-auto-reload.sh` 使用 `inotifywait` 监听证书文件变化，续签完成后自动执行 `nginx -s reload`，无需手动重启容器。
5. 如需排查签发失败，可执行 `docker compose logs cert_automation` 查看详细日志，并核对 Cloudflare Token 是否具备 `Zone.DNS` 编辑权限。

> 更多变量说明与调试建议见 [docs/TLS_CERT_AUTOMATION.md](docs/TLS_CERT_AUTOMATION.md)。

`infra/nginx/conf.d/sublink.upstream.conf` 的核心配置片段如下：

```nginx
server {
    listen 80;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    ssl_certificate     /etc/nginx/ssl/fullchain.cer;
    ssl_certificate_key /etc/nginx/ssl/private.key;

    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port 443;
    }
}
```

## Cloudflare 设置

1. **SSL/TLS 模式**：在 Cloudflare 控制台将域名的 SSL/TLS 模式设置为 **Full (strict)**，确保 Cloudflare 与源站之间使用有效证书。
2. **DNS 记录**：为 `yet.la` 与 `*.yet.la` 创建 A/AAAA 记录指向服务器公网 IP。常规运行可保持「代理状态」开启（橙色云朵）。
3. **排障模式**：若需绕过 Cloudflare 验证源站，可将记录切换为「DNS only」（灰色云朵），待问题排查完成后再恢复代理。
4. **防火墙与速率限制**：可在 Cloudflare 配置允许列表或速率限制，限制 `/admin` 与 `/api/*` 的访问来源。

## 部署完成后的使用方式

### 管理后台

- 入口：`https://<你的域名>/admin`
- 认证：支持登录页表单或 HTTP Basic，两者都会将身份信息写入服务器端会话；默认凭据为 `admin/admin`（可通过环境变量覆盖或在后台修改）。
- 功能：通过 HTMX 调用 `/api/links`、`/api/subdomains` 与 `/api/users` 完成 CRUD，并提供「修改密码」「设置」入口；界面组件在移动端下自动折叠为单列视图，便于手机端运维。
- 设置页：管理员可调整基础域名、管理域名列表、短链默认长度、路径前缀以及站点的 Logo/Icon，所有变更即时写入数据库并影响前端展示与访问逻辑。
- 屏蔽名单：设置页新增「管理子域屏蔽名单」卡片，可批量维护保留前缀并实时刷新表格，普通用户提交与修改子域时会自动校验。

### 访客访问

- `https://yet.la/`：根据子域匹配结果返回重定向或 404 文本。
- `https://yet.la/<code>`（或自定义路径前缀，如 `/r/<code>`）：短链接入口，命中后累积访问次数。

## 子域屏蔽名单与长度限制

- **预置保留前缀**：后端启动时会调用 `ensure_default_subdomain_blacklist`，将 `www`、`mail`、`api`、`admin`、`login`、`cdn` 等常见敏感前缀写入 `subdomain_blacklist` 表，确保首次部署即可阻止误用。
- **界面与 API 管控**：管理员可在后台「设置」页直接编辑屏蔽名单文本框，或通过 `/api/subdomain-blacklist` 系列接口批量同步；保存后相关 HTMX 片段会自动刷新，列表保持最新状态。
- **普通账号限制**：非管理员创建或修改子域时，后端会校验前缀长度需在 3-20 个字符之间，并拒绝使用屏蔽名单中的任何前缀；管理员在必要时可绕过限制并协助调整目标域名。

## 管理域名列表与短链域控制

- **统一管理域名**：`backend/app/settings_service.py` 将 `site_settings.managed_domains` 作为空格分隔的域名集合进行持久化，首个域名视为平台主域，其余域名可用于短链跳转与访客访问。
- **主域名职责**：主域名既是后台表单默认选项，也是所有对外展示文案（如导航 Logo 下的域名说明、帮助提示）所引用的唯一域名。即便列表中维护了多个域名，对外呈现的品牌域名也只会展示主域名，避免对用户造成混淆。
- **自动归一化**：提交的域名会去掉协议、路径与大小写差异，并去重后回写数据库；系统同时生成 `www.` 互通的映射，确保 `example.com` 与 `www.example.com` 都可命中短链。
- **创建短链**：后台表单与 `/api/links` 接口支持传入 `domain` 字段选择要使用的域名，留空则默认采用主域名。域名必须存在于管理列表中，普通用户不可越权创建其他域名的短链。
- **部署初始化**：通过环境变量 `BASE_DOMAIN` 可一次性写入多个初始域名（以空格或逗号分隔），容器首次启动时会自动归一化并保存到数据库，可在后台「设置」页继续调整。

## API 说明与示例 curl

`backend/app/main.py` 提供以下接口：

| Method | Path | 说明 | 认证 | 常见返回码 |
| --- | --- | --- | --- | --- |
| GET | `/healthz` | 健康检查 | 无 | 200 |
| GET | `/routes` | 查询所有子域跳转规则 | 无 | 200 |
| GET | `/api/links` | 列出短链接 | 需要登录 | 200 |
| POST | `/api/links` | 新增短链接（`code` 为空时自动生成） | 需要登录 | 201 / 409 |
| PUT | `/api/links/{id}` | 更新短链接（支持修改 code、域名与目标地址） | 需要登录 | 200 / 404 / 409 |
| DELETE | `/api/links/{id}` | 删除短链接 | 需要登录 | 204 / 404 |
| GET | `/api/subdomains` | 列出子域跳转 | 需要登录 | 200 |
| POST | `/api/subdomains` | 新增子域跳转（`host` 为完整域名） | 需要登录 | 201 / 409 |
| PUT | `/api/subdomains/{id}` | 更新子域跳转（含 Host/URL/状态码） | 需要登录 | 200 / 404 / 409 |
| DELETE | `/api/subdomains/{id}` | 删除子域跳转 | 需要登录 | 204 / 404 |
| GET | `/api/subdomain-blacklist` | 查看子域屏蔽名单 | 需要管理员权限 | 200 |
| POST | `/api/subdomain-blacklist` | 新增单个屏蔽前缀 | 需要管理员权限 | 201 / 409 |
| PUT | `/api/subdomain-blacklist` | 批量替换屏蔽名单（空格分隔） | 需要管理员权限 | 200 / 422 |
| DELETE | `/api/subdomain-blacklist/{id}` | 删除屏蔽名单条目 | 需要管理员权限 | 204 / 404 |
| GET | `/api/users` | 列出平台用户（管理员限定） | 需要管理员权限 | 200 |
| POST | `/api/users` | 创建用户（支持设置管理员角色） | 需要管理员权限 | 201 / 409 |
| PUT | `/api/users/{id}` | 更新用户资料与密码 | 需要管理员权限 | 200 / 400 / 404 / 409 |
| DELETE | `/api/users/{id}` | 删除用户（至少保留一名管理员） | 需要管理员权限 | 204 / 400 / 404 |
| GET | `/api/settings` | 读取站点设置 | 需要管理员权限 | 200 |
| PUT/POST | `/api/settings` | 更新站点设置 | 需要管理员权限 | 200 |
| POST | `/api/users/me/password` | 当前登录用户修改密码 | 需要登录 | 204 / 400 / 404 |
| GET | `/{code}` | 短链接跳转并累积访问量 | 无 | 302 / 404 |
| ANY | `/{path}` | 根据 `Host` 匹配子域跳转，未命中则返回 404 文本 | 无 | 30x / 404 |

写操作同时支持 JSON 与表单提交，示例如下：

```bash
# JSON 请求体
curl -sk -u admin:changeme \
  -H "Content-Type: application/json" \
  -d '{"target_url":"https://example.com/landing","code":"promo","domain":"go.example.com"}' \
  https://yet.la/api/links

# application/x-www-form-urlencoded
curl -sk -u admin:changeme \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "host=foo.yet.la&target_url=https://example.com&code=301" \
  https://yet.la/api/subdomains

# 批量替换子域屏蔽名单
curl -sk -u admin:changeme \
  -H "Content-Type: application/json" \
  -d '{"labels":"www api admin marketing"}' \
  https://yet.la/api/subdomain-blacklist

# multipart/form-data
curl -sk -u admin:changeme \
  -F "target_url=https://example.org/signup" \
  -F "code=winter" \
  -F "domain=go.yet.la" \
  https://yet.la/api/links
```

常见状态码说明：

| 状态码 | 含义 |
| --- | --- |
| `200/201` | 写入成功，响应体包含创建或更新后的对象。 |
| `401` | 缺少或错误的 Basic Auth 凭据，响应附带 `WWW-Authenticate: Basic`。 |
| `409` | 唯一键冲突（如短链 code 或子域已存在），请求不会写入数据库。 |
| `404` | 目标资源不存在或未配置子域跳转。 |
| `422` | 请求参数不合法，响应包含字段级错误信息。 |

## 环境变量

核心站点配置（基础域名、短链路径、Logo/Icon、默认长度）已持久化到数据库，并可在后台「设置」页面实时调整。以下环境变量仅在首次启动或批量部署时生效，可按需覆盖默认值：

| 变量名 | 说明 |
| --- | --- |
| `ADMIN_USER` | 初始管理员用户名（默认 `admin`，启动后会写入数据库）。 |
| `ADMIN_PASS` | 初始管理员密码（默认 `admin`，建议首登后修改）。 |
| `BASE_DOMAIN` | （可选）首次初始化时的管理域名列表，例如 `yet.la go.yet.la` 或 `yet.la,go.yet.la`；首个域名会作为主域名写入数据库。 |
| `SHORT_CODE_LEN` | （可选）首次初始化时的短链默认长度，后台设置页可随时调整。 |
| `SHORT_LINK_PATH` | （可选）首次初始化时的短链路径前缀，例如 `/` 或 `/r/`。 |
| `SITE_LOGO_URL` | （可选）首次初始化时的站点 Logo 地址。 |
| `SITE_ICON_URL` | （可选）首次初始化时的站点 Icon 地址。 |
| `DATABASE_URL` | SQLAlchemy 兼容的数据库连接串，默认为 `sqlite:////data/data.db`。可指向外部 PostgreSQL/MySQL。 |
| `SESSION_SECRET` | 管理后台的服务器端会话密钥，默认回退为 `ADMIN_PASS`。生产环境务必覆盖。 |

## 数据存储

- 后端默认使用 SQLite，数据库位于容器内 `/data/data.db`；若设置 `DATABASE_URL`，会自动创建对应目录或连接外部数据库。
- `docker-compose.yml` 将仓库根目录的 `./data` 挂载到容器 `/data`，FastAPI 在启动钩子中确保目录存在并创建表结构以及历史数据库的补丁字段（如 `hits` 统计列、`users` 表及外键关系）。
- 子域与短链都会累积访问次数，可在后台界面查看；建议定期备份 `data/data.db` 或目标数据库，可参考 [docs/backup-example.sh](docs/backup-example.sh)。

## 安全基线

- **强化 Basic Auth 凭据**：使用长度 ≥ 16 的随机密码，并定期轮换。
- **限制来源 IP**：在 Cloudflare、防火墙或前置负载均衡层对白名单 IP 开放 `/admin` 与 `/api/*`。
- **日志与备份**：将 `./data` 与容器日志纳入备份计划，可配合 cron 定期执行备份脚本。

## 测试运行

后端自带 Pytest 用例验证核心逻辑：

```bash
# 本机安装依赖后执行
pip install -r backend/requirements.txt
pytest -q

# 或在已运行的 Docker 容器中执行
docker compose exec backend pytest -q
```

## 常见故障排障

| 现象 | 可能原因 | 排查建议 |
| --- | --- | --- |
| Cloudflare 返回 `521` | 源站拒绝连接或 TLS 不匹配 | 确认容器已启动、`docker compose ps` 无异常；Cloudflare SSL/TLS 模式是否为 **Full (strict)**；临时切换 DNS-only 直接访问 `https://<源站IP>` 验证。 |
| 浏览器报 `ERR_SSL_PROTOCOL_ERROR` | 使用 HTTPS 访问 `:8080` 或证书尚未签发 | 仅开放 `80/443`，通过 `docker compose logs cert_automation` 排查签发日志，并确认卷 `/etc/nginx/ssl/fullchain.cer`、`private.key` 已生成且权限正确。 |
| API 返回 `401 Unauthorized` | Basic Auth 凭据缺失或错误 | 确认请求头是否包含 `Authorization: Basic ...`，并检查 `.env` 中的 `ADMIN_USER`/`ADMIN_PASS`。 |
| 创建记录时报 `409 Conflict` | 违反唯一约束（短链 code 或子域重复） | 调整请求中的 `code` 或 `host`，亦可调用 `GET /api/...` 查看现有记录。 |
| 访问子域返回 `404` | 未配置对应跳转或 Host 头未透传 | 在 Nginx/负载均衡层确认 `Host` 头保留原始值，必要时通过 `curl -H "Host: foo.yet.la" https://yet.la/` 排查。 |

遇到其他问题，可结合 `docker compose logs nginx` 与 `docker compose logs backend` 查看详细日志。
