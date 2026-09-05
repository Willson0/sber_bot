import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.handlers import router
from core.config import get_settings


logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    settings = get_settings()

    if not settings.bot_token:
        raise RuntimeError(
            "BOT_TOKEN не задан. Добавь токен бота в файл .env"
        )

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    dp.include_router(router)

    logger.info("Бот запущен. Ожидание сообщений...")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())