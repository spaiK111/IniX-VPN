import html
import logging
import os
import random
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


def get_marzban_user(username: str, token: str | None = None) -> dict | None:
    """Looks up a Marzban user by username. Returns None if it doesn't exist."""
    token = token or get_marzban_token()
    resp = requests.get(
        f"{MARZBAN_API_URL}/api/user/{username}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def find_user_by_telegram_id(telegram_id: int, token: str | None = None) -> dict | None:
    """Finds the Marzban user whose `note` field holds this Telegram ID.

    We can't use the Telegram ID as the Marzban username directly since new
    accounts get a random numeric username instead, so the note field is
    the only link between the two.
    """
    token = token or get_marzban_token()
    resp = requests.get(
        f"{MARZBAN_API_URL}/api/users",
        headers={"Authorization": f"Bearer {token}"},
        params={"search": str(telegram_id)},
        timeout=10,
    )
    resp.raise_for_status()
    for user in resp.json().get("users", []):
        if user.get("note") == str(telegram_id):
            return user
    return None


def create_disabled_user_for_telegram(telegram_id: int, token: str | None = None) -> dict:
    """Creates a new Marzban user (random numeric username) for a first-time
    bot user, with a vless proxy already configured but status=disabled
    until an admin activates it."""
    token = token or get_marzban_token()

    for _ in range(5):
        username = str(random.randint(10**8, 10**9 - 1))
        resp = requests.post(
            f"{MARZBAN_API_URL}/api/user",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "username": username,
                "proxies": {"vless": {"flow": "xtls-rprx-vision"}},
                "inbounds": {"vless": ["VLESS TCP REALITY"]},
                "expire": 0,
                "data_limit": 0,
                "data_limit_reset_strategy": "no_reset",
                "status": "active",
                "note": str(telegram_id),
            },
            timeout=10,
        )
        if resp.status_code == 409:
            continue  # username collision, retry with a new random one
        resp.raise_for_status()
        break
    else:
        raise RuntimeError("Could not find a free random username after 5 tries")

    disable_resp = requests.put(
        f"{MARZBAN_API_URL}/api/user/{username}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "disabled"},
        timeout=10,
    )
    disable_resp.raise_for_status()
    return disable_resp.json()


def build_link_text(user: dict, telegram_id: int) -> str:
    links = user.get("links") or []
    if not links:
        return f"Telegram-ID: {telegram_id}\n\n{NO_LINK_TEXT}"

    expire = user.get("expire")
    expire_text = "unbegrenzt" if not expire else time.strftime("%d.%m.%Y", time.localtime(expire))
    used_mb = (user.get("used_traffic") or 0) / 1024 / 1024

    # <code> makes the link monospace and tap-to-copy in Telegram's mobile apps.
    return (
        f"Telegram-ID: {telegram_id}\n"
        f"Status: {user.get('status', 'unknown').capitalize()}\n\n"
        f"Dein VPN-Link (antippen zum Kopieren):\n<code>{html.escape(links[0])}</code>\n\n"
        f"Gueltig bis: {expire_text}\n"
        f"Verbrauch bisher: {used_mb:.1f} MB"
    )


def build_status_text(user: dict) -> str:
    lines = [f"Status: {user.get('status', 'unknown').capitalize()}"]

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
    telegram_id = update.effective_user.id
    try:
        token = get_marzban_token()
        user = find_user_by_telegram_id(telegram_id, token)
        if user is None:
            user = create_disabled_user_for_telegram(telegram_id, token)
            text = (
                f"Telegram-ID: {telegram_id}\n"
                f"Status: {user.get('status', 'unknown').capitalize()}\n\n"
                "Dein Account wurde angelegt, ist aber noch nicht freigeschaltet. "
                "Melde dich beim Admin."
            )
        else:
            text = (
                f"Telegram-ID: {telegram_id}\n"
                f"Status: {user.get('status', 'unknown').capitalize()}"
            )
    except Exception as e:
        log.exception("start command failed")
        text = f"Fehler: {html.escape(str(e))}"

    await update.message.reply_text(text, reply_markup=MENU_KEYBOARD, parse_mode="HTML")


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    try:
        user = find_user_by_telegram_id(telegram_id)
        text = build_link_text(user, telegram_id) if user else f"Telegram-ID: {telegram_id}\n\n{NO_LINK_TEXT}"
    except Exception as e:
        log.exception("link command failed")
        text = f"Fehler beim Abrufen: {html.escape(str(e))}"
    await update.message.reply_text(text, reply_markup=MENU_KEYBOARD, parse_mode="HTML")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    try:
        user = find_user_by_telegram_id(telegram_id)
        text = build_status_text(user) if user else NO_LINK_TEXT
    except Exception as e:
        log.exception("status command failed")
        text = f"Fehler beim Abrufen: {html.escape(str(e))}"
    await update.message.reply_text(text, reply_markup=MENU_KEYBOARD, parse_mode="HTML")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id

    try:
        user = find_user_by_telegram_id(telegram_id)
        if query.data == "link":
            text = build_link_text(user, telegram_id) if user else f"Telegram-ID: {telegram_id}\n\n{NO_LINK_TEXT}"
        elif query.data == "status":
            text = build_status_text(user) if user else NO_LINK_TEXT
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
