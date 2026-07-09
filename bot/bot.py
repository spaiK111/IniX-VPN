import logging
import os
import socket
import time

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vpn-bot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ["TELEGRAM_ALLOWED_USER_ID"])

MARZBAN_API_URL = os.environ.get("MARZBAN_API_URL", "http://127.0.0.1:8000")
MARZBAN_ADMIN_USERNAME = os.environ["MARZBAN_ADMIN_USERNAME"]
MARZBAN_ADMIN_PASSWORD = os.environ["MARZBAN_ADMIN_PASSWORD"]
VPN_USERNAME = os.environ.get("VPN_USERNAME", "maks")

SERVER_PUBLIC_IP = os.environ["SERVER_PUBLIC_IP"]
SERVER_PORT = int(os.environ.get("SERVER_PORT", "443"))


def is_authorized(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == ALLOWED_USER_ID


def get_marzban_token() -> str:
    resp = requests.post(
        f"{MARZBAN_API_URL}/api/admin/token",
        data={"username": MARZBAN_ADMIN_USERNAME, "password": MARZBAN_ADMIN_PASSWORD},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "VPN-Bot bereit.\n\n"
        "/link - deinen VPN-Link abrufen\n"
        "/status - Serverstatus pruefen"
    )


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    try:
        token = get_marzban_token()
        resp = requests.get(
            f"{MARZBAN_API_URL}/api/user/{VPN_USERNAME}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        links = data.get("links") or []
        if not links:
            await update.message.reply_text("Kein Link fuer diesen Nutzer gefunden.")
            return

        expire = data.get("expire")
        expire_text = "unbegrenzt" if not expire else time.strftime("%d.%m.%Y", time.localtime(expire))
        used_mb = (data.get("used_traffic") or 0) / 1024 / 1024

        await update.message.reply_text(
            f"Dein VPN-Link:\n{links[0]}\n\n"
            f"Gueltig bis: {expire_text}\n"
            f"Verbrauch bisher: {used_mb:.1f} MB"
        )
    except Exception as e:
        log.exception("link command failed")
        await update.message.reply_text(f"Fehler beim Abrufen: {e}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    lines = []

    try:
        get_marzban_token()
        lines.append("Marzban-Panel: erreichbar")
    except Exception:
        lines.append("Marzban-Panel: NICHT erreichbar")

    try:
        start_t = time.monotonic()
        with socket.create_connection((SERVER_PUBLIC_IP, SERVER_PORT), timeout=5):
            pass
        latency_ms = (time.monotonic() - start_t) * 1000
        lines.append(f"VPN-Port {SERVER_PORT}: erreichbar ({latency_ms:.0f} ms Antwortzeit)")
    except Exception:
        lines.append(f"VPN-Port {SERVER_PORT}: NICHT erreichbar")

    await update.message.reply_text("\n".join(lines))


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("link", link))
    app.add_handler(CommandHandler("status", status))
    log.info("Bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
