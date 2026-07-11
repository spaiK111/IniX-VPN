# INIX VPN

A self-hosted VPN service built on [Marzban](https://github.com/Gozargah/Marzban) / [Xray-core](https://github.com/XTLS/Xray-core), with a custom branded subscription page and a Telegram bot for self-service account management.

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
   │ Marzban (HTTPS)  │ │              Xray-core                    │
   │ 127.0.0.1:8443   │ │  VLESS+Reality   127.0.0.1:8444 (→:443)   │
   │ - Admin panel    │ │  VMess+TLS       0.0.0.0:8880             │
   │ - Subscription   │ │  Trojan+TLS      0.0.0.0:2096              │
   │   pages (/sub/*) │ │  Shadowsocks     0.0.0.0:8388              │
   │ - REST API       │ └──────────────────────────────────────────┘
   └────────┬─────────┘
            │ REST API (localhost)
            │
   ┌────────┴─────────┐        ┌──────────────────────┐
   │   Telegram Bot     │◄─────►│   MongoDB Atlas        │
   │  (polling, no      │       │  supplementary user     │
   │   public port)     │       │  bookkeeping             │
   └────────────────────┘       └──────────────────────┘
```

The VPS runs three things behind a single public IP:

1. **nginx** owns ports 80 and 443. On 443 it does TLS-unaware SNI routing (`ssl_preread`) - it never terminates TLS itself for VPN traffic, it just peeks at the requested hostname in the TLS ClientHello and forwards the raw byte stream:
   - SNI `inix-vpn.com` → Marzban's own HTTPS listener (admin panel, subscription pages)
   - Anything else (including Reality's decoy SNI, `www.cloudflare.com`) → Xray's VLESS+Reality inbound

   Port 80 only serves ACME HTTP-01 challenges for Let's Encrypt certificate renewal (`certbot renew`, webroot method).

2. **Marzban** (running inside a custom Docker image, see [`Dockerfile`](Dockerfile)) manages Xray-core's configuration and users, and serves:
   - The admin dashboard (`/dashboard/`)
   - The REST API used by the Telegram bot
   - Per-user subscription pages (`/sub/<token>`) using the custom template in [`templates/subscription/index.html`](templates/subscription/index.html)
   - Static assets for that page (`/assets/*`, patched into Marzban since it has no built-in static file serving - see the Dockerfile)

3. **The Telegram bot** ([`bot/`](bot/)) is a separate container that talks to Marzban's API over localhost. It never listens on a public port (long-polling only).

## Supported protocols

Every user gets all four, each on its own port:

| Protocol | Port | Notes |
|---|---|---|
| VLESS + Reality | 443 (via nginx) | Primary protocol - mimics real TLS traffic to a decoy site (`www.cloudflare.com`), no certificate needed, hardest to block |
| VMess + TLS | 8880 | Uses the real `inix-vpn.com` certificate |
| Trojan + TLS | 2096 | Uses the real `inix-vpn.com` certificate |
| Shadowsocks | 8388 | No TLS; AEAD-encrypted |

## Telegram bot

Source: [`bot/bot.py`](bot/bot.py), translations in [`bot/i18n.py`](bot/i18n.py) (English/German/Russian).

- `/start` - looks up the caller's Marzban account by their Telegram ID (stored in Marzban's `note` field, since usernames are random numeric IDs, not the Telegram ID itself). If none exists, it auto-creates one with all 4 protocols configured but `status: disabled`, pending manual admin approval.
- **Info** - shows the VPN link(s), expiry and traffic usage.
- **Status** - checks whether the Marzban panel and the VPN port respond.
- **Connect** - a direct link button to the user's subscription page, only shown when their Marzban status is `active`.
- **Language** - persists a per-user language choice (English/German/Russian) via `PicklePersistence`, mounted on a volume so it survives redeploys.

Every `/start` also upserts a record in a MongoDB `users` collection (`telegram_id`, `marzban_username`, `subscription_type`, `subscription_status`, timestamps). This is a **supplementary bookkeeping store only** - Marzban remains the sole source of truth for actual VPN access. A MongoDB outage is logged and swallowed; it never blocks `/start`.

## Subscription page

Custom-built (not Marzban's default template) to match a dark, branded design. Split into:

- [`templates/subscription/index.html`](templates/subscription/index.html) - Jinja2 template (Marzban's templating engine), structure only
- [`assets/subscription.css`](assets/subscription.css) - all styling
- [`assets/subscription.js`](assets/subscription.js) - all behavior (protocol tabs, copy-to-clipboard, QR codes, platform/app-specific install guides)

Dynamic data (the per-protocol links) is passed from the template to the script via a `<script type="application/json">` block rather than being spliced into executable JavaScript - keeps Jinja template syntax out of any context where a JS/CSS-aware tool would try to parse it as the target language.

The install guide covers Android, iOS, Windows, macOS and Linux, each with its own set of apps and per-app step-by-step instructions.

## CI/CD

[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml): on every push to `main`,

1. Builds and pushes two images to GHCR: `ghcr.io/spaik111/vpn-service` (Marzban) and `ghcr.io/spaik111/vpn-service-bot` (the bot)
2. SSHes into the VPS and runs `docker compose pull && docker compose up -d`

Both GHCR packages are public (no secrets baked into either image - the private key, admin credentials, bot token and MongoDB URI all live in `.env` / `bot.env` on the VPS only, outside of git).

## Repository layout

```
Dockerfile                        # Marzban image: pins Xray-core version, patches for
                                   # compatibility + static asset serving
docker-compose.yml                # marzban + telegram-bot services (deployed as-is to the VPS)
bot/
  bot.py                          # Telegram bot
  i18n.py                         # EN/DE/RU translations
  Dockerfile
  requirements.txt
templates/subscription/index.html # Custom subscription page template
assets/
  subscription.css
  subscription.js
  logo.png
.github/workflows/deploy.yml      # Build + deploy pipeline
```

## Not tracked in git (live only on the VPS)

- `.env` / `bot.env` - secrets (Marzban admin password, Telegram bot token, MongoDB URI, etc.)
- `/var/lib/marzban/xray_config.json` - Xray inbound config (contains the Reality private key)
- `/etc/letsencrypt/` - TLS certificates (mounted read-only into the Marzban container)
- nginx config (`/etc/nginx/stream.conf`, `/etc/nginx/sites-available/inix-vpn.com`) - the SNI routing and ACME webroot setup were configured directly on the server, not via this repo

## Known trade-offs

- The Marzban `/code/app/xray/core.py` and `/code/app/__init__.py` patches (x25519 output-format compatibility, static asset mount) are applied at Docker build time via inline Python in the `Dockerfile`, not upstream changes - if Marzban's source changes structurally, these patches may need updating.
- Install-guide app links point to App Store / Play Store **search results**, not hardcoded product IDs, to avoid linking to a wrong app if an exact ID is ever misremembered.
