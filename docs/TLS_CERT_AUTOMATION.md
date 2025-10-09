# TLS 证书自动签发与续期指南

SubLink 内置 `cert_automation` 容器，会按照后台配置的域名自动申请与轮换 TLS 证书。本指南介绍服务工作原理、所需环境变量以及常见调试方法。

> 提示：通过 `bash <(curl -Ls "https://raw.githubusercontent.com/maiizii/sublink/main/install.sh")` 执行一键脚本时，系统会主动引导填写 `BASE_DOMAIN`、`CF_DNS_API_TOKEN` 与可选的 `ACME_ACCOUNT_EMAIL`，无需手动编辑 `.env`。

## 工作原理概览

1. `docker-compose.yml` 启动 `cert_automation` 容器，镜像位于 `infra/cert-automation`。
2. 容器读取 `.env` 中的 `BASE_DOMAIN`、`CERTBOT_ADDITIONAL_DOMAINS` 并连接 SQLite 数据库获取后台「设置」页保存的 `managed_domains`。
3. 收集到的域名会扩展出对应的泛域名（`*.example.com`），随后通过 Cloudflare DNS-01 流程向 ACME 服务（默认 Let's Encrypt 生产环境）申请证书。
4. 证书成功签发或续签后会写入共享卷 `/etc/nginx/ssl/fullchain.cer` 与 `/etc/nginx/ssl/private.key`，Nginx 入口脚本会立即检测到更新并执行 `nginx -s reload`。
5. 如后台域名列表发生变化，容器会触发强制续签，确保证书始终覆盖最新配置。

## 必填环境变量

| 变量 | 说明 |
| --- | --- |
| `BASE_DOMAIN` | 初始管理域名列表，支持空格或逗号分隔多个域名。首次启动时会同步到数据库，供证书申请与后台默认配置使用。 |
| `CF_DNS_API_TOKEN` | Cloudflare Scoped API Token，需具备目标 Zone 的 `Zone.DNS` **Edit** 权限。 |

## 可选变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ACME_ACCOUNT_EMAIL` | （空） | 用于接收证书到期提醒的邮箱，留空则通过 `--register-unsafely-without-email` 注册，请自行关注证书有效期。 |
| `CERTBOT_ADDITIONAL_DOMAINS` | （空） | 额外需要覆盖的域名，格式与 `BASE_DOMAIN` 相同。适用于需要同一证书覆盖多套环境的情况。 |
| `ACME_DIRECTORY` | `https://acme-v02.api.letsencrypt.org/directory` | ACME 目录地址，可改为 Let's Encrypt Staging 或其他 CA（如使用 ZeroSSL 需同时设置 `ACME_EAB_KID` 与 `ACME_EAB_HMAC_KEY`）。 |
| `CF_DNS_PROPAGATION_SECONDS` | `60` | 等待 Cloudflare DNS TXT 记录生效的时长（秒）。若区域 DNS 更新较慢可适当调大。 |
| `CERTBOT_CHECK_INTERVAL_SECONDS` | `43200` | 证书检查与续签的轮询周期（秒）。默认 12 小时检查一次。 |

## 日志与排障

- 查看实时日志：
  ```bash
  docker compose logs -f cert_automation
  ```
- 常见报错排查：
  - `no domains configured`：尚未在 `.env` 或后台设置任何域名；请填写 `BASE_DOMAIN` 并确保后台 **设置 → 管理域名** 中存在有效域名。
  - `Incorrect Cloudflare API token`：确认 Token 拥有目标 Zone 的 DNS 编辑权限，必要时重新生成最小权限的 Scoped Token。
  - `NXDOMAIN` 或 `SERVFAIL`：Cloudflare DNS 记录尚未生效，可调整 `CF_DNS_PROPAGATION_SECONDS` 或等待数十秒后自动重试。
- 查看当前证书覆盖的域名：
  ```bash
  openssl x509 -in /etc/nginx/ssl/fullchain.cer -noout -text | grep -A1 "Subject Alternative Name"
  ```
  （可在宿主机通过 `docker compose exec nginx` 进入容器后执行。）

## 更新域名或令牌

- 修改后台 **设置 → 管理域名** 后，`cert_automation` 会自动检测变更并强制续签。
- 若需要替换 Cloudflare Token，可更新 `.env` 后执行：
  ```bash
  docker compose up -d cert_automation
  ```
  容器会重新读取环境变量并触发下一次轮询。
- 更换 ACME 目录或通知邮箱后同样执行上述命令即可生效。

## 常见问题

| 问题 | 原因 | 处理建议 |
| --- | --- | --- |
| Nginx 启动超时 | 证书尚未生成，入口脚本在等待 | 通过 `docker compose logs cert_automation` 查看签发进度，确认证书成功写入 `/etc/nginx/ssl`。 |
| 证书未覆盖新增域名 | 后台修改后未触发续签或失败 | 检查日志中是否包含 `force-renewal` 记录以及 Cloudflare API 是否返回成功。必要时删除共享卷 `certbot_state` 重新申请。 |
| 希望在测试环境使用自签证书 | 当前容器默认使用 ACME 申请，若需自签可暂时停用 `cert_automation`，手动在 `/etc/nginx/ssl` 写入自签证书后重启 Nginx。 |

通过上述配置即可实现证书的自动申请与无感续期，完全避免将私钥纳入仓库或手动操作。
