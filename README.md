# INIX VPN

A self-hosted VPN service built on [Remnawave](https://github.com/remnawave/panel) / [Xray-core](https://github.com/XTLS/Xray-core), with a Telegram bot for self-service account management.

## Architecture

```
                              ┌─────────────────────────────┐
                              │        Internet users       │
                              └───────────┬──────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │ :443 (SNI routing)   │ :8880 / :2096 / :8388│  :80 (ACME only)
                    ▼                     │                      ▼
         ┌─────────────────┐              │            ┌──────────────────┐
         │      nginx       │              │            │  nginx (webroot)  │
         │  ssl_preread on  │              │            │ certbot renewal   │
         └──┬───────────┬───┘              │            └──────────────────┘
   SNI ==    │           │  SNI != inix-vpn.com
inix-vpn.com │           │  (Reality decoy / anything else)
            ▼           ▼                  │
   ┌─────────────────┐ ┌──────────────────────────────────────────┐
   │ Traefik (HTTPS)  │ │           Remnawave Node (Xray-core)      │
   │ 127.0.0.1:8543   │ │  VLESS+Reality   127.0.0.1:8444 (→:443)   │
   └────────┬─────────┘ │  Hysteria2       0.0.0.0:8880 (udp)       │
            │           │  Trojan+TLS      0.0.0.0:2096              │
            ▼           │  Shadowsocks     0.0.0.0:8388              │
   ┌─────────────────┐  └──────────────────────────────────────────┘
   │ Remnawave Panel  │             ▲
   │ - Admin panel    │             │ control channel (:2222)
   │ - REST API       │◄────────────┘
   │ - /api/sub/*     │
   └────────┬─────────┘
            │ Postgres + Redis (internal)
            │ REST API (public, HTTPS)
            │
   ┌────────┴─────────┐        ┌──────────────────────┐
   │   Telegram Bot     │◄─────►│   MongoDB Atlas        │
   │  (polling, no      │       │  supplementary user     │
   │   public port)     │       │  bookkeeping             │
   └────────────────────┘       └──────────────────────┘
```

The VPS runs the following behind a single public IP:

1. **nginx** owns ports 80 and 443. On 443 it does TLS-unaware SNI routing (`ssl_preread`) - it never terminates TLS itself for VPN traffic, it just peeks at the requested hostname in the TLS ClientHello and forwards the raw byte stream:
   - SNI `inix-vpn.com` → Traefik, which terminates TLS (real Let's Encrypt cert) and reverse-proxies to the Remnawave Panel
   - Anything else (including Reality's decoy SNI, `www.cloudflare.com`) → the Remnawave Node's VLESS+Reality inbound

   Port 80 only serves ACME HTTP-01 challenges for Let's Encrypt certificate renewal (`certbot renew`, webroot method).

2. **Remnawave** is split into two containers, unlike Marzban's single-container design:
   - **Panel** (`remnawave/backend`, + Postgres + Redis) - the admin dashboard, REST API, and the `/api/sub/<shortUuid>` subscription endpoint that VPN clients (e.g. Happ) fetch directly. Reachable only through Traefik - Remnawave's `ProxyCheckMiddleware` rejects any request that doesn't come through a properly configured reverse proxy with forwarded headers.
   - **Node** (`remnawave/node`) - runs Xray-core itself and the actual protocol inbounds. Runs with `network_mode: host` (it needs to bind real proxy ports directly) and is addressed by the Panel via the VPS's public IP over a private control port (`2222`).

   Both are colocated on the same VPS as Marzban was. Traefik uses its **file provider** (static YAML, no Docker socket needed) rather than Docker-based service discovery.

3. **The Telegram bot** ([`bot/`](bot/)) is a separate container that talks to the Panel's public HTTPS API (`https://inix-vpn.com`) - it can't call the Panel directly over the internal Docker network because of the reverse-proxy check mentioned above. It never listens on a public port itself (long-polling only).

Remnawave's default subscription page (`remnawave/subscription-page`) is deployed on the VPS for internal testing but not yet exposed publicly - the bot and VPN clients use the raw `/api/sub/<shortUuid>` subscription URL directly, which is enough for apps like Happ to import all protocols. Wiring up a public, branded subscription page is a possible follow-up.

## Supported protocols

Every user gets all four, each on its own port:

| Protocol | Port | Notes |
|---|---|---|
| VLESS + Reality | 443 (via nginx) | Primary protocol - mimics real TLS traffic to a decoy site (`www.cloudflare.com`), no certificate needed, hardest to block |
| Hysteria2 | 8880 (udp) | QUIC-based; uses the real `inix-vpn.com` certificate. Replaces VMess, which Remnawave's Xray-core build doesn't support |
| Trojan + TLS | 2096 | Uses the real `inix-vpn.com` certificate |
| Shadowsocks | 8388 | No TLS; AEAD-encrypted |

## Telegram bot

Source: [`bot/bot.py`](bot/bot.py), translations in [`bot/i18n.py`](bot/i18n.py) (English/German/Russian).

- `/start` - looks up the caller's Remnawave account by their Telegram ID, using Remnawave's native `telegramId` field (unlike Marzban, which had no such field and needed the free-text `note` field as a workaround). If none exists, it auto-creates one assigned to the production internal squad but `status: DISABLED`, pending manual admin approval.
- **Info** - shows the subscription URL (paste into a VPN client app), expiry and traffic usage.
- **Status** - checks whether the Remnawave panel and the VPN port respond.
- **Connect** - a direct link button to the user's subscription URL, only shown when their Remnawave status is `ACTIVE`.
- **Language** - persists a per-user language choice (English/German/Russian) via `PicklePersistence`, mounted on a volume so it survives redeploys.

Every `/start` also upserts a record in a MongoDB `users` collection (`telegram_id`, `marzban_username` - historical field name, holds the Remnawave username, `subscription_type`, `subscription_status`, timestamps). This is a **supplementary bookkeeping store only** - Remnawave remains the sole source of truth for actual VPN access. A MongoDB outage is logged and swallowed; it never blocks `/start`.

## CI/CD

[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml): on every push to `main`,

1. Builds and pushes the bot image to GHCR: `ghcr.io/spaik111/vpn-service-bot`
2. SSHes into the VPS and runs `docker compose pull && docker compose up -d` in `/opt/remnawave`

The Remnawave Panel/Node/Traefik/Postgres/Redis stack itself is *not* built or deployed by this pipeline - it runs official upstream images (no custom patches needed, unlike Marzban), managed directly on the VPS via compose files under `/opt/remnawave/` that aren't tracked in this repo.

The GHCR package is public (no secrets baked into the image - the bot token, Remnawave API token and MongoDB URI all live in `bot.env` on the VPS only, outside of git).

## Repository layout

```
docker-compose.yml                # telegram-bot service (deployed as-is to the VPS, /opt/remnawave)
bot/
  bot.py                          # Telegram bot
  i18n.py                         # EN/DE/RU translations
  Dockerfile
  requirements.txt
assets/
  logo.png                        # kept for a future branded subscription page
.github/workflows/deploy.yml      # Build + deploy pipeline (bot only)
```

## Not tracked in git (live only on the VPS)

- `bot.env` - secrets (Telegram bot token, Remnawave API token, MongoDB URI, etc.)
- `/opt/remnawave/` - the Remnawave stack's compose files, `.env` (Postgres/Redis/JWT secrets), Traefik config
- `/etc/letsencrypt/` - TLS certificates (mounted read-only into the Traefik and Node containers)
- nginx config (`/etc/nginx/stream.conf`, `/etc/nginx/sites-available/inix-vpn.com`) - the SNI routing and ACME webroot setup were configured directly on the server, not via this repo
- `/var/lib/marzban/` - the old Marzban SQLite database and Xray config, kept only as a historical record of pre-migration user data; no longer used by anything running

## Known trade-offs

- Remnawave's Xray-core build doesn't support VMess at all (hard validation error, not just undocumented) - Hysteria2 was chosen as the replacement 4th protocol.
- The subscription page is Remnawave's unmodified default (no custom branding yet, and not yet exposed publicly) - branding parity with the old custom-built design (dark theme, per-platform install guide) is a deferred follow-up.
