import html
import logging
import os
import random
import socket
import time

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    PicklePersistence,
)

from i18n import DEFAULT_LANG, TRANSLATIONS, status_label, t

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vpn-bot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

MARZBAN_API_URL = os.environ.get("MARZBAN_API_URL", "http://127.0.0.1:8000")
MARZBAN_ADMIN_USERNAME = os.environ["MARZBAN_ADMIN_USERNAME"]
MARZBAN_ADMIN_PASSWORD = os.environ["MARZBAN_ADMIN_PASSWORD"]

SERVER_PUBLIC_IP = os.environ["SERVER_PUBLIC_IP"]
SERVER_PORT = int(os.environ.get("SERVER_PORT", "443"))

PERSISTENCE_PATH = os.environ.get("PERSISTENCE_PATH", "/data/bot_persistence.pkl")

LANGUAGE_LABELS = {"ru": "🇷🇺 Русский", "de": "🇩🇪 Deutsch", "en": "🇬🇧 English"}


def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)


def _connect_row(lang: str, subscription_url: str | None) -> list:
    if not subscription_url:
        return []
    return [InlineKeyboardButton(t(lang, "btn_connect"), url=subscription_url)]


def home_keyboard(lang: str, subscription_url: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(t(lang, "btn_info"), callback_data="link"),
            InlineKeyboardButton(t(lang, "btn_status"), callback_data="status"),
        ],
    ]
    connect_row = _connect_row(lang, subscription_url)
    if connect_row:
        rows.append(connect_row)
    rows.append([InlineKeyboardButton(t(lang, "btn_language"), callback_data="language")])
    return InlineKeyboardMarkup(rows)


def result_keyboard(lang: str, subscription_url: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(t(lang, "btn_info"), callback_data="link"),
            InlineKeyboardButton(t(lang, "btn_status"), callback_data="status"),
        ],
    ]
    connect_row = _connect_row(lang, subscription_url)
    if connect_row:
        rows.append(connect_row)
    rows.append([InlineKeyboardButton(t(lang, "btn_home"), callback_data="home")])
    return InlineKeyboardMarkup(rows)


def language_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"lang_{code}") for code, label in LANGUAGE_LABELS.items()],
        [InlineKeyboardButton(t(lang, "btn_home"), callback_data="home")],
    ])


def get_marzban_token() -> str:
    resp = requests.post(
        f"{MARZBAN_API_URL}/api/admin/token",
        data={"username": MARZBAN_ADMIN_USERNAME, "password": MARZBAN_ADMIN_PASSWORD},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


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


def get_or_create_user(telegram_id: int) -> tuple[dict, bool]:
    """Returns (user, was_just_created)."""
    token = get_marzban_token()
    user = find_user_by_telegram_id(telegram_id, token)
    if user is not None:
        return user, False
    return create_disabled_user_for_telegram(telegram_id, token), True


def build_home_text(lang: str, user: dict, telegram_id: int, just_created: bool) -> str:
    text = (
        f"{t(lang, 'telegram_id')}: {telegram_id}\n"
        f"{t(lang, 'status')}: {status_label(lang, user.get('status', 'unknown'))}"
    )
    if just_created:
        text += f"\n\n{t(lang, 'pending_activation')}"
    return text


def build_link_text(lang: str, user: dict, telegram_id: int) -> str:
    links = user.get("links") or []
    if not links:
        return f"{t(lang, 'telegram_id')}: {telegram_id}\n\n{t(lang, 'no_link')}"

    expire = user.get("expire")
    expire_text = t(lang, "unlimited") if not expire else time.strftime("%d.%m.%Y", time.localtime(expire))
    used_mb = (user.get("used_traffic") or 0) / 1024 / 1024

    # <code> makes the link monospace and tap-to-copy in Telegram's mobile apps.
    return (
        f"{t(lang, 'telegram_id')}: {telegram_id}\n"
        f"{t(lang, 'status')}: {status_label(lang, user.get('status', 'unknown'))}\n\n"
        f"{t(lang, 'link_header')}\n<code>{html.escape(links[0])}</code>\n\n"
        f"{t(lang, 'valid_until')}: {expire_text}\n"
        f"{t(lang, 'usage_so_far')}: {used_mb:.1f} MB"
    )


def build_status_text(lang: str, user: dict) -> str:
    lines = [f"{t(lang, 'status')}: {status_label(lang, user.get('status', 'unknown'))}"]

    try:
        get_marzban_token()
        lines.append(t(lang, "panel_reachable"))
    except Exception:
        lines.append(t(lang, "panel_unreachable"))

    try:
        start_t = time.monotonic()
        with socket.create_connection((SERVER_PUBLIC_IP, SERVER_PORT), timeout=5):
            pass
        latency_ms = (time.monotonic() - start_t) * 1000
        lines.append(t(lang, "port_reachable", port=SERVER_PORT, ms=latency_ms))
    except Exception:
        lines.append(t(lang, "port_unreachable", port=SERVER_PORT))

    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    telegram_id = update.effective_user.id
    sub_url = None
    try:
        user, just_created = get_or_create_user(telegram_id)
        text = build_home_text(lang, user, telegram_id, just_created)
        sub_url = user.get("subscription_url")
    except Exception as e:
        log.exception("start command failed")
        text = f"{t(lang, 'error')}: {html.escape(str(e))}"
    await update.message.reply_text(text, reply_markup=home_keyboard(lang, sub_url), parse_mode="HTML")


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    telegram_id = update.effective_user.id
    sub_url = None
    try:
        user = find_user_by_telegram_id(telegram_id)
        if user:
            text = build_link_text(lang, user, telegram_id)
            sub_url = user.get("subscription_url")
        else:
            text = f"{t(lang, 'telegram_id')}: {telegram_id}\n\n{t(lang, 'no_link')}"
    except Exception as e:
        log.exception("link command failed")
        text = f"{t(lang, 'error_fetching')}: {html.escape(str(e))}"
    await update.message.reply_text(text, reply_markup=result_keyboard(lang, sub_url), parse_mode="HTML")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    telegram_id = update.effective_user.id
    sub_url = None
    try:
        user = find_user_by_telegram_id(telegram_id)
        text = build_status_text(lang, user) if user else t(lang, "no_link")
        sub_url = user.get("subscription_url") if user else None
    except Exception as e:
        log.exception("status command failed")
        text = f"{t(lang, 'error_fetching')}: {html.escape(str(e))}"
    await update.message.reply_text(text, reply_markup=result_keyboard(lang, sub_url), parse_mode="HTML")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    telegram_id = update.effective_user.id

    try:
        if query.data == "home":
            user, just_created = get_or_create_user(telegram_id)
            text = build_home_text(lang, user, telegram_id, just_created)
            keyboard = home_keyboard(lang, user.get("subscription_url"))

        elif query.data == "language":
            text = t(lang, "choose_language")
            keyboard = language_keyboard(lang)

        elif query.data.startswith("lang_"):
            new_lang = query.data.removeprefix("lang_")
            if new_lang not in TRANSLATIONS:
                return
            context.user_data["lang"] = new_lang
            text = t(new_lang, "language_set")
            keyboard = home_keyboard(new_lang)

        else:
            user = find_user_by_telegram_id(telegram_id)
            sub_url = user.get("subscription_url") if user else None
            keyboard = result_keyboard(lang, sub_url)
            if query.data == "link":
                text = (
                    build_link_text(lang, user, telegram_id)
                    if user
                    else f"{t(lang, 'telegram_id')}: {telegram_id}\n\n{t(lang, 'no_link')}"
                )
            elif query.data == "status":
                text = build_status_text(lang, user) if user else t(lang, "no_link")
            else:
                return
    except Exception as e:
        log.exception("button callback failed")
        text = f"{t(lang, 'error_fetching')}: {html.escape(str(e))}"
        keyboard = result_keyboard(lang)

    await query.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


def main():
    persistence = PicklePersistence(filepath=PERSISTENCE_PATH)
    app = Application.builder().token(BOT_TOKEN).persistence(persistence).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("link", link))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(button))
    log.info("Bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
