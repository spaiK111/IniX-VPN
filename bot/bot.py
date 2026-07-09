import html
import logging
import os
import socket
import time

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vpn-bot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

MARZBAN_API_URL = os.environ.get("MARZBAN_API_URL", "http://127.0.0.1:8000")
MARZBAN_ADMIN_USERNAME = os.environ["MARZBAN_ADMIN_USERNAME"]
MARZBAN_ADMIN_PASSWORD = os.environ["MARZBAN_ADMIN_PASSWORD"]

SERVER_PUBLIC_IP = os.environ["SERVER_PUBLIC_IP"]
SERVER_PORT = int(os.environ.get("SERVER_PORT", "443"))

NO_LINK_TEXT = "You currently dont have a vpn link"

MENU_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("ℹ️ Info", callback_data="link"),
        InlineKeyboardButton("📡 Status", callback_data="status"),
    ]
])


def get_marzban_token() -> str:
    resp = requests.post(
        f"{MARZBAN_API_URL}/api/admin/token",
        data={"username": MARZBAN_ADMIN_USERNAME, "password": MARZBAN_ADMIN_PASSWORD},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_marzban_user(username: str) -> dict | None:
    """Looks up a Marzban user by username. Returns None if it doesn't exist."""
    token = get_marzban_token()
    resp = requests.get(
        f"{MARZBAN_API_URL}/api/user/{username}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def build_link_text(telegram_id: int) -> str:
    data = get_marzban_user(str(telegram_id))
    if data is None:
        return f"Telegram-ID: {telegram_id}\n\n{NO_LINK_TEXT}"

    links = data.get("links") or []
    if not links:
        return f"Telegram-ID: {telegram_id}\n\n{NO_LINK_TEXT}"

    expire = data.get("expire")
    expire_text = "unbegrenzt" if not expire else time.strftime("%d.%m.%Y", time.localtime(expire))
    used_mb = (data.get("used_traffic") or 0) / 1024 / 1024

    # <code> makes the link monospace and tap-to-copy in Telegram's mobile apps.
    return (
        f"Telegram-ID: {telegram_id}\n\n"
        f"Dein VPN-Link (antippen zum Kopieren):\n<code>{html.escape(links[0])}</code>\n\n"
        f"Gueltig bis: {expire_text}\n"
        f"Verbrauch bisher: {used_mb:.1f} MB"
    )


def build_status_text(telegram_id: int) -> str:
    if get_marzban_user(str(telegram_id)) is None:
        return NO_LINK_TEXT

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

    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hey, what do you want to know?", reply_markup=MENU_KEYBOARD)


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = build_link_text(update.effective_user.id)
    except Exception as e:
        log.exception("link command failed")
        text = f"Fehler beim Abrufen: {html.escape(str(e))}"
    await update.message.reply_text(text, reply_markup=MENU_KEYBOARD, parse_mode="HTML")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = build_status_text(update.effective_user.id)
    except Exception as e:
        log.exception("status command failed")
        text = f"Fehler beim Abrufen: {html.escape(str(e))}"
    await update.message.reply_text(text, reply_markup=MENU_KEYBOARD, parse_mode="HTML")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        if query.data == "link":
            text = build_link_text(update.effective_user.id)
        elif query.data == "status":
            text = build_status_text(update.effective_user.id)
        else:
            return
    except Exception as e:
        log.exception("button callback failed")
        text = f"Fehler beim Abrufen: {html.escape(str(e))}"

    await query.message.reply_text(text, reply_markup=MENU_KEYBOARD, parse_mode="HTML")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("link", link))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(button))
    log.info("Bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
