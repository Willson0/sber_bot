from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from core.config import get_settings, is_webapp_configured


def main_keyboard() -> ReplyKeyboardMarkup:
    settings = get_settings()

    if is_webapp_configured(settings):
        find_button = KeyboardButton(
            text="🔍 Найти подписки",
            web_app=WebAppInfo(url=settings.webapp_url.strip()),
        )
    else:
        find_button = KeyboardButton(text="🔍 Найти подписки")

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[find_button]],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Нажми, чтобы открыть сканер подписок",
    )

    return keyboard