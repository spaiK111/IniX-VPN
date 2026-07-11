import html
import logging
import os
import random
import socket
import time
from datetime import datetime, timezone

import requests
from pymongo import MongoClient
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

REMNAWAVE_API_URL = os.environ.get("REMNAWAVE_API_URL", "http://127.0.0.1:3000")
REMNAWAVE_API_TOKEN = os.environ["REMNAWAVE_API_TOKEN"]
REMNAWAVE_DEFAULT_SQUAD_UUID = os.environ["REMNAWAVE_DEFAULT_SQUAD_UUID"]
REMNAWAVE_VERIFY_TLS = os.environ.get("REMNAWAVE_VERIFY_TLS", "true").lower() != "false"

# Remnawave requires a concrete expireAt date (no "0 = unlimited" like Marzban had).
# Accounts meant to never expire get this far-future sentinel instead; anything at
# or beyond this year is displayed as "unlimited".
UNLIMITED_EXPIRE_YEAR = 2099
UNLIMITED_EXPIRE_AT = datetime(UNLIMITED_EXPIRE_YEAR, 1, 1, tzinfo=timezone.utc)

SERVER_PUBLIC_IP = os.environ["SERVER_PUBLIC_IP"]
SERVER_PORT = int(os.environ.get("SERVER_PORT", "443"))

PERSISTENCE_PATH = os.environ.get("PERSISTENCE_PATH", "/data/bot_persistence.pkl")

LANGUAGE_LABELS = {"ru": "🇷🇺 Русский", "de": "🇩🇪 Deutsch", "en": "🇬🇧 English"}

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DB = os.environ.get("MONGODB_DB", "inix_vpn")

mongo_users_collection = None
if MONGODB_URI:
    try:
        _mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        mongo_users_collection = _mongo_client[MONGODB_DB]["users"]
    except Exception:
        log.exception("Failed to initialize MongoDB client")


def find_mongo_user(telegram_id: int) -> dict | None:
    """Looks up the existing MongoDB record for this Telegram user, if any."""
    if mongo_users_collection is None:
        return None
    try:
        return mongo_users_collection.find_one({"telegram_id": telegram_id})
    except Exception:
        log.exception("Failed to look up MongoDB user %s", telegram_id)
        return None


def upsert_mongo_user(telegram_id: int, remnawave_username: str, remnawave_status: str) -> None:
    """Creates or updates the MongoDB record for this Telegram user.

    On first creation, subscription_status mirrors the freshly created
    Remnawave account (inactive/disabled until an admin approves it). For
    users that already exist, their stored subscription_status is left
    untouched here - it's a business-level field an admin may set
    independently of Remnawave's technical status.

    Best-effort: MongoDB is a supplementary bookkeeping store, not the
    source of truth for VPN access (Remnawave is), so a Mongo outage must
    never break /start.
    """
    if mongo_users_collection is None:
        return
    try:
        now = datetime.now(timezone.utc)
        initial_status = "active" if remnawave_status == "ACTIVE" else "inactive"
        mongo_users_collection.update_one(
            {"telegram_id": telegram_id},
            {
                "$set": {
                    "marzban_username": remnawave_username,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "telegram_id": telegram_id,
                    "subscription_type": "free",
                    "subscription_status": initial_status,
                    "created_at": now,
                },
            },
            upsert=True,
        )
    except Exception:
        log.exception("Failed to upsert MongoDB user %s", telegram_id)


def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", DEFAULT_LANG)


def connect_url_for(user: dict | None) -> str | None:
    """Only surface the Connect button for users whose Remnawave status is
    actually 'ACTIVE' — disabled/pending/expired/limited accounts don't get
    a usable connection, so linking them there would be misleading."""
    if not user or user.get("status") != "ACTIVE":
        return None
    return user.get("subscriptionUrl")


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


def _remnawave_headers() -> dict:
    return {"Authorization": f"Bearer {REMNAWAVE_API_TOKEN}"}


def find_user_by_telegram_id(telegram_id: int) -> dict | None:
    """Finds the Remnawave user with this Telegram ID.

    Unlike Marzban (which had no such field and needed the `note` field as a
    workaround), Remnawave has a native `telegramId` column with a dedicated
    lookup endpoint.
    """
    resp = requests.get(
        f"{REMNAWAVE_API_URL}/api/users/by-telegram-id/{telegram_id}",
        headers=_remnawave_headers(),
        timeout=10,
        verify=REMNAWAVE_VERIFY_TLS,
    )
    resp.raise_for_status()
    users = resp.json().get("response") or []
    return users[0] if users else None


def create_disabled_user_for_telegram(telegram_id: int) -> dict:
    """Creates a new Remnawave user (random numeric username) for a first-time
    bot user, with the default protocol squad already assigned but
    status=DISABLED until an admin activates it."""
    for _ in range(5):
        username = str(random.randint(10**8, 10**9 - 1))
        resp = requests.post(
            f"{REMNAWAVE_API_URL}/api/users",
            headers=_remnawave_headers(),
            json={
                "username": username,
                "status": "DISABLED",
                "telegramId": telegram_id,
                "expireAt": UNLIMITED_EXPIRE_AT.isoformat().replace("+00:00", "Z"),
                "trafficLimitBytes": 0,
                "trafficLimitStrategy": "NO_RESET",
                "activeInternalSquads": [REMNAWAVE_DEFAULT_SQUAD_UUID],
            },
            timeout=10,
            verify=REMNAWAVE_VERIFY_TLS,
        )
        if resp.status_code == 400 and "already exists" in resp.text:
            continue  # username collision, retry with a new random one
        resp.raise_for_status()
        return resp.json()["response"]
    raise RuntimeError("Could not find a free random username after 5 tries")


def get_or_create_user(telegram_id: int) -> tuple[dict, bool]:
    """Returns (user, was_just_created)."""
    user = find_user_by_telegram_id(telegram_id)
    just_created = user is None
    if just_created:
        user = create_disabled_user_for_telegram(telegram_id)
    upsert_mongo_user(telegram_id, user["username"], user.get("status", "DISABLED"))
    return user, just_created


def build_home_text(lang: str, user: dict, telegram_id: int, just_created: bool) -> str:
    text = (
        f"{t(lang, 'telegram_id')}: {telegram_id}\n"
        f"{t(lang, 'status')}: {status_label(lang, user.get('status', 'unknown').lower())}"
    )
    if just_created:
        text += f"\n\n{t(lang, 'pending_activation')}"
    return text


def build_link_text(lang: str, user: dict, telegram_id: int) -> str:
    subscription_url = user.get("subscriptionUrl")
    if not subscription_url:
        return f"{t(lang, 'telegram_id')}: {telegram_id}\n\n{t(lang, 'no_link')}"

    expire_at = user.get("expireAt")
    expire_text = t(lang, "unlimited")
    if expire_at:
        parsed = datetime.fromisoformat(expire_at.replace("Z", "+00:00"))
        if parsed.year < UNLIMITED_EXPIRE_YEAR:
            expire_text = parsed.strftime("%d.%m.%Y")
    used_mb = (user.get("userTraffic", {}).get("usedTrafficBytes") or 0) / 1024 / 1024

    # <code> makes the link monospace and tap-to-copy in Telegram's mobile apps.
    return (
        f"{t(lang, 'telegram_id')}: {telegram_id}\n"
        f"{t(lang, 'status')}: {status_label(lang, user.get('status', 'unknown').lower())}\n\n"
        f"{t(lang, 'link_header')}\n<code>{html.escape(subscription_url)}</code>\n\n"
        f"{t(lang, 'valid_until')}: {expire_text}\n"
        f"{t(lang, 'usage_so_far')}: {used_mb:.1f} MB"
    )


def build_status_text(lang: str, user: dict) -> str:
    lines = [f"{t(lang, 'status')}: {status_label(lang, user.get('status', 'unknown').lower())}"]

    try:
        resp = requests.get(
            f"{REMNAWAVE_API_URL}/api/system/health",
            headers=_remnawave_headers(),
            timeout=10,
            verify=REMNAWAVE_VERIFY_TLS,
        )
        resp.raise_for_status()
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
        sub_url = connect_url_for(user)
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
            sub_url = connect_url_for(user)
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
        sub_url = connect_url_for(user)
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
            keyboard = home_keyboard(lang, connect_url_for(user))

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
            sub_url = connect_url_for(user)
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
