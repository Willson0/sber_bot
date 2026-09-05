from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards import main_keyboard
from core.config import get_settings, is_webapp_configured


router = Router()


WELCOME_TEXT = (
    "Привет! Я помогу найти платные подписки, которые списывают деньги.\n\n"
    "Загрузи банковскую выписку за 6 месяцев, и я найду регулярные списания, "
    "посчитаю сумму в месяц и возможную экономию за год.\n\n"
    "Нажми «Найти подписки», чтобы открыть приложение."
)


MINI_APP_NOT_READY_TEXT = (
    "Mini App ещё не подключён.\n\n"
    "Чтобы кнопка открывала приложение, укажи в файле .env переменную WEBAPP_URL "
    "с HTTPS-ссылкой на страницу приложения.\n\n"
    "Сейчас можно продолжить разработку без неё."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_keyboard(),
    )


@router.message(F.text == "🔍 Найти подписки")
async def find_subscriptions(message: Message) -> None:
    settings = get_settings()

    if is_webapp_configured(settings):
        await message.answer(
            "Открываю сканер подписок.\n"
            "Если приложение не открылось, нажми кнопку ещё раз."
        )
    else:
        await message.answer(MINI_APP_NOT_READY_TEXT)