TRANSLATIONS = {
    "en": {
        "telegram_id": "Telegram ID",
        "status": "Status",
        "pending_activation": "Your account was created but is not activated yet. Please contact the admin.",
        "no_link": "You currently dont have a vpn link",
        "link_header": "Your VPN link (tap to copy):",
        "valid_until": "Valid until",
        "unlimited": "unlimited",
        "usage_so_far": "Usage so far",
        "panel_reachable": "VPN panel: reachable",
        "panel_unreachable": "VPN panel: NOT reachable",
        "port_reachable": "VPN port {port}: reachable ({ms:.0f} ms response time)",
        "port_unreachable": "VPN port {port}: NOT reachable",
        "btn_info": "ℹ️ Info",
        "btn_status": "📡 Status",
        "btn_home": "🏠 Home",
        "btn_language": "🌐 Language",
        "btn_connect": "🔌 Connect",
        "choose_language": "Choose your Language",
        "language_set": "Language set to English 🇬🇧",
        "error": "Error",
        "error_fetching": "Error while fetching",
        "status_values": {
            "active": "Active",
            "disabled": "Disabled",
            "limited": "Limited",
            "expired": "Expired",
            "on_hold": "On hold",
        },
    },
    "de": {
        "telegram_id": "Telegram-ID",
        "status": "Status",
        "pending_activation": "Dein Account wurde angelegt, ist aber noch nicht freigeschaltet. Melde dich beim Admin.",
        "no_link": "Du hast aktuell keinen VPN-Link",
        "link_header": "Dein VPN-Link (antippen zum Kopieren):",
        "valid_until": "Gueltig bis",
        "unlimited": "unbegrenzt",
        "usage_so_far": "Verbrauch bisher",
        "panel_reachable": "VPN-Panel: erreichbar",
        "panel_unreachable": "VPN-Panel: NICHT erreichbar",
        "port_reachable": "VPN-Port {port}: erreichbar ({ms:.0f} ms Antwortzeit)",
        "port_unreachable": "VPN-Port {port}: NICHT erreichbar",
        "btn_info": "ℹ️ Info",
        "btn_status": "📡 Status",
        "btn_home": "🏠 Home",
        "btn_language": "🌐 Sprache",
        "btn_connect": "🔌 Verbinden",
        "choose_language": "Waehle deine Sprache",
        "language_set": "Sprache auf Deutsch gestellt 🇩🇪",
        "error": "Fehler",
        "error_fetching": "Fehler beim Abrufen",
        "status_values": {
            "active": "Aktiv",
            "disabled": "Deaktiviert",
            "limited": "Limitiert",
            "expired": "Abgelaufen",
            "on_hold": "Wartend",
        },
    },
    "ru": {
        "telegram_id": "Telegram ID",
        "status": "Статус",
        "pending_activation": "Ваш аккаунт создан, но еще не активирован. Свяжитесь с администратором.",
        "no_link": "У вас пока нет VPN-ссылки",
        "link_header": "Ваша VPN-ссылка (нажмите, чтобы скопировать):",
        "valid_until": "Действителен до",
        "unlimited": "неограниченно",
        "usage_so_far": "Использовано",
        "panel_reachable": "VPN-панель: доступна",
        "panel_unreachable": "VPN-панель: НЕДОСТУПНА",
        "port_reachable": "VPN-порт {port}: доступен ({ms:.0f} мс время отклика)",
        "port_unreachable": "VPN-порт {port}: НЕДОСТУПЕН",
        "btn_info": "ℹ️ Инфо",
        "btn_status": "📡 Статус",
        "btn_home": "🏠 Домой",
        "btn_language": "🌐 Язык",
        "btn_connect": "🔌 Подключиться",
        "choose_language": "Выберите язык",
        "language_set": "Язык изменен на Русский 🇷🇺",
        "error": "Ошибка",
        "error_fetching": "Ошибка при получении данных",
        "status_values": {
            "active": "Активен",
            "disabled": "Отключен",
            "limited": "Лимит исчерпан",
            "expired": "Истек",
            "on_hold": "Ожидание",
        },
    },
}

DEFAULT_LANG = "en"


def t(lang: str, key: str, **kwargs) -> str:
    strings = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG])
    text = strings.get(key, TRANSLATIONS[DEFAULT_LANG].get(key, key))
    return text.format(**kwargs) if kwargs else text


def status_label(lang: str, status: str) -> str:
    strings = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG])
    return strings["status_values"].get(status, status.capitalize())
