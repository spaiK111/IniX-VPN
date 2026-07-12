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
   ┌──────────────────┐ ┌──────────────────────────────────────────┐
   │ Traefik (HTTPS)   │ │           Remnawave Node (Xray-core)      │
   │ 127.0.0.1:8543    │ │  VLESS+Reality   127.0.0.1:8444 (→:443)   │
   │ Host-based route  │ │  Hysteria2       0.0.0.0:8880 (udp)       │
   └──┬────────────┬───┘ │  Trojan+TLS      0.0.0.0:2096              │
      │            │     │  Shadowsocks     0.0.0.0:8388              │
      ▼            ▼     └──────────────────────────────────────────┘
   ┌─────────┐ ┌───────────────┐               ▲
   │Remnawave │ │ Subscription   │               │ control channel (:2222)
   │Panel     │ │ page           │               │
   │- Admin UI│ │ (HTML or raw   │◄──────────────┘
   │- REST API│◄┤  config, based │
   │- /api/*  │ │  on requester) │
   └────┬─────┘ └───────────────┘
        │ Postgres + Redis (internal)
        │ REST API (public, HTTPS)
        │
   ┌────┴──────────────┐        ┌──────────────────────┐
   │   Telegram Bot      │◄─────►│   MongoDB Atlas        │
   │  (polling, no       │       │  supplementary user     │
   │   public port)      │       │  bookkeeping             │
   └─────────────────────┘       └──────────────────────┘
```

The VPS runs the following behind a single public IP:

1. **nginx** owns ports 80 and 443. On 443 it does TLS-unaware SNI routing (`ssl_preread`) - it never terminates TLS itself for VPN traffic, it just peeks at the requested hostname in the TLS ClientHello and forwards the raw byte stream:
   - SNI `inix-vpn.com` or `sub.inix-vpn.com` → Traefik, which terminates TLS (real Let's Encrypt certs, one per domain) and reverse-proxies by `Host` header to the Panel or the subscription page respectively
   - Anything else (including Reality's decoy SNI, `www.cloudflare.com`) → the Remnawave Node's VLESS+Reality inbound

   Port 80 only serves ACME HTTP-01 challenges for Let's Encrypt certificate renewal (`certbot renew`, webroot method) for both domains.

2. **Remnawave** is split into three containers, unlike Marzban's single-container design:
   - **Panel** (`remnawave/backend`, + Postgres + Redis) - the admin dashboard and REST API. Reachable only through Traefik - Remnawave's `ProxyCheckMiddleware` rejects any request that doesn't come through a properly configured reverse proxy with forwarded headers.
   - **Node** (`remnawave/node`) - runs Xray-core itself and the actual protocol inbounds. Runs with `network_mode: host` (it needs to bind real proxy ports directly) and is addressed by the Panel via the VPS's public IP over a private control port (`2222`).
   - **Subscription page** (`remnawave/subscription-page`) - a separate frontend, on its own subdomain (`sub.inix-vpn.com`), that turns a subscription link into either a browsable HTML page (QR codes, per-platform install info) or a raw config, depending on who's asking - see below.

   All three are colocated on the same VPS as Marzban was. Traefik uses its **file provider** (static YAML, no Docker socket needed) rather than Docker-based service discovery.

3. **The Telegram bot** ([`bot/`](bot/)) is a separate container that talks to the Panel's public HTTPS API (`https://inix-vpn.com`) - it can't call the Panel directly over the internal Docker network because of the reverse-proxy check mentioned above. It never listens on a public port itself (long-polling only).

Every user's `subscriptionUrl` looks like `https://sub.inix-vpn.com/<shortUuid>` - a single link that serves two different things from the same URL, based on the requester:

- **A browser** (the bot's "Connect" button, or a link tapped by hand) gets the subscription page's rendered HTML - status, traffic, expiry, and (depending on config) QR codes/install instructions.
- **A VPN client** (Happ, v2rayNG, etc., identified by `Accept`/`User-Agent`) gets the raw base64/YAML config with the actual connection details for all 4 protocols.

The subscription page needs its **own subdomain** rather than sharing a path on `inix-vpn.com` - it was tried first (`PathPrefix(/sub)` + `CUSTOM_SUB_PREFIX`), but both the Panel's dashboard and the subscription page serve their static JS/CSS bundles from an identical, non-configurable `/assets/*` path, so path-based routing made one of them load the other's (broken) assets. A separate `Host()` rule per subdomain avoids the collision entirely, at the cost of one extra DNS record and Let's Encrypt certificate. The subscription page also gate-checks `/assets/*` and `/locales/*` requests against a short-lived session cookie set on the initial page load (anti-hotlinking) - this only matters if you're testing it with `curl`, real browsers carry the cookie automatically. The Panel's own lower-level endpoint, `/api/sub/<shortUuid>` on `inix-vpn.com`, still exists directly and keeps working (older imported links using it, e.g. from before the subscription page was wired up, don't break).

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
2. Copies the whole [`remnawave/`](remnawave/) directory to `/opt/remnawave/` on the VPS (`appleboy/scp-action`, plain recursive copy - only adds/overwrites the files it brings, never deletes anything already there, so the real `.env` files that live only on the server are never touched)
3. SSHes in and runs `docker compose -f <file> up -d` for each stack, in dependency order (`docker-compose-prod.yml` first - it's what creates the shared `remnawave-network` the others join), then pulls and restarts the bot

The Remnawave Panel/Node/Traefik/Postgres/Redis/subscription-page stack runs official upstream images - no custom patches or builds needed (unlike Marzban), just `image:` references in the compose files. `docker compose up -d` is idempotent: nothing gets recreated unless its config actually changed.

The GHCR bot package is public (no secrets baked into the image - the bot token, Remnawave API token and MongoDB URI all live in `bot.env` on the VPS only, outside of git).

## Repository layout

```
remnawave/
  docker-compose.yml            # telegram-bot
  docker-compose-prod.yml       # Panel + Postgres + Redis (official Remnawave file)
  docker-compose.traefik.yml    # reverse proxy (file provider, no Docker socket)
  docker-compose.node.yml       # Xray-core node
  docker-compose.branding.yml   # tiny nginx:alpine serving the Panel logo
  docker-compose.subpage.yml    # subscription page
  traefik-dynamic.yml           # Traefik routing rules + TLS cert paths
  branding/logo.svg             # served at https://inix-vpn.com/branding/logo.svg
  xray/refresh-zapret.sh        # daily cron script, see "RU Zapret blocklist" below
  .env.sample                   # Panel secrets template
  bot.env.sample
  node.env.sample
  subpage.env.sample
bot/
  bot.py                        # Telegram bot
  i18n.py                       # EN/DE/RU translations
  Dockerfile
  requirements.txt
assets/
  logo.png                      # unused leftover from the Marzban-era subscription page
.github/workflows/deploy.yml    # Build + deploy pipeline
```

## Not tracked in git (live only on the VPS)

- `/opt/remnawave/.env`, `bot.env`, `node.env`, `subpage.env` - real secrets (Postgres/Redis/JWT secrets, Telegram bot token, Remnawave API tokens, node cert/key bundle, MongoDB URI). Each has a `*.env.sample` counterpart in [`remnawave/`](remnawave/) documenting the required keys.
- `/opt/remnawave/xray/share/zapret.dat` - the actual blocklist data (~35MB), downloaded by `refresh-zapret.sh` (which *is* tracked) rather than committed
- `/etc/letsencrypt/` - TLS certificates (mounted read-only into the Traefik and Node containers)
- nginx config (`/etc/nginx/stream.conf`, `/etc/nginx/sites-available/inix-vpn.com`) - the SNI routing and ACME webroot setup were configured directly on the server, not via this repo
- `/var/lib/marzban/` - the old Marzban SQLite database and Xray config, kept only as a historical record of pre-migration user data; no longer used by anything running

## RU Zapret blocklist

The production config profile's Xray routing blackholes two domain lists from [`kutovoys/ru_gov_zapret`](https://github.com/kutovoys/ru_gov_zapret) (`ext:zapret.dat:zapret` - domains blocked in Russia by Roskomnadzor, and `:zapret-zapad` - foreign resources that don't serve Russian IPs). This isn't about restricting what our users can reach - it's server self-protection: DPI systems used for Russian internet filtering are known to probe suspicious servers by testing whether they'll route traffic to known-RKN-blocked domains, and a VPN node that happily does so is a more visible target for getting its own IP blocked. Refusing to route there makes the node less interesting to that kind of probe.

Mechanically: `zapret.dat` is downloaded to `/opt/remnawave/xray/share/` on the VPS and bind-mounted read-only into the `remnanode` container at `/usr/local/bin/zapret.dat` (see [`remnawave/docker-compose.node.yml`](remnawave/docker-compose.node.yml)). The production config profile's `routing.rules` references it by that filename - that part lives in Remnawave's database, set via the API, not in any file here. A daily cron job (`0 4 * * *`, logs to `/var/log/zapret-refresh.log`, script at [`remnawave/xray/refresh-zapret.sh`](remnawave/xray/refresh-zapret.sh)) re-downloads the file, and only if it actually changed, replaces it and force-restarts the node so Xray-core reloads it.

## Known trade-offs

- Remnawave's Xray-core build doesn't support VMess at all (hard validation error, not just undocumented) - Hysteria2 was chosen as the replacement 4th protocol.
- The subscription page is Remnawave's unmodified default (no custom branding) - visual parity with the old custom-built design (dark theme, per-platform install guide) is a deferred follow-up.
