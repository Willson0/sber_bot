import asyncio
from aiogram import Dispatcher, types, F
from bot import bot
import datetime
import io
import os
import re
import logging
from integrations.hydraai import TextAI
from subscription_finder import build_llm_payload
from aiogram.filters import Command
import json
from utils import make_subscriptions_keyboard, parse_statement
from database import init_db, save_statement, get_statement, close_pool
from llm_helpers import call_llm_with_retry, llm_failed
from aiogram.types import BufferedInputFile
from subscription_finder import build_llm_payload, find_matching_transactions
from chart_generator import compute_subscription_stats, render_stats_card

dp = Dispatcher()

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
   filename='logs/pdf_extract.log',
   filemode='a',
   format='%(asctime)s | %(levelname)s | %(message)s',
   level=logging.INFO,
   encoding='utf-8'
)


async def main():
    cmds = [
        types.BotCommand(command="start", description="Главное меню"),
    ]
    await bot.set_my_commands(commands=cmds)
    await dp.start_polling(bot, allowed_updates=["message", 'callback_query'])


@dp.startup()
async def startup():
    await init_db()
    me = await bot.get_me()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"\n"
        f"====================[ Telegram Bot Started ]====================\n"
        f"🟢 Бот успешно запущен!\n"
        f"📅 Дата запуска: {now}\n"
        f"🤖 Имя: {me.first_name}\n"
        f"🔗 Username: @{me.username}\n"
        f"🆔 Bot ID: {me.id}\n"
        f"🌐 Интеграция: HydraAI\n"
        f"===============================================================\n"
    )


@dp.message(Command("start"))
async def start_command_handler(message: types.Message):
    with open('start_message.txt', 'r', encoding='utf-8') as f:
        start = f.read()
    await bot.send_rich_message(chat_id=message.chat.id, rich_message=types.InputRichMessage(markdown=start, parse_mode="Markdown"))


def clean_record(r: dict) -> dict:
    """Универсальная очистка для обоих форматов (sber/tbank)"""
    amount_str = str(r.get('amount', '')).replace('\u00a0', '').replace(' ', '').replace(',', '.')
    try:
        amount = float(amount_str)
    except ValueError:
        amount = None

    sign = r.get('sign')
    if sign == '-' and amount is not None:
        amount = -abs(amount)
    elif sign == '+' and amount is not None:
        amount = abs(amount)

    return {
        'date': r.get('date'),
        'time': r.get('time', ''),
        'category': r.get('category', ''),
        'amount': amount,
        'desc': re.sub(r'\s+', ' ', r.get('desc', '')).strip(),
    }


@dp.message(F.document)
async def pdf_handler(message: types.Message):
    document = message.document
    if not document.file_name.lower().endswith('.pdf'):
        await message.reply("Пожалуйста, отправьте файл формата .pdf")
        return

    mes = await message.answer("Генерирую ответ по вашему PDF...")

    # Скачиваем файл
    file = await bot.get_file(document.file_id)
    file_bytes = await bot.download_file(file.file_path)

    if isinstance(file_bytes, bytes):
        file_content = io.BytesIO(file_bytes)
    else:
        file_bytes.seek(0)
        file_content = file_bytes

    try:
        bank, records = parse_statement(file_content)
    except Exception as e:
        await mes.edit_text(f"Ошибка чтения PDF: {e}")
        return

    if not records:
        await mes.edit_text("Не удалось извлечь транзакции из PDF.")
        return

    records = [clean_record(r) for r in records]

    # ── Детерминированная предобработка: находим кластеры-кандидаты
    # на подписку ДО того, как отдать что-либо LLM.
    clusters = build_llm_payload(records)

    logging.info("Raw records: %d, clusters found: %d", len(records), len(clusters))

    # Если алгоритм вообще не нашёл ни одного повтора/маркера — сразу
    # отдаём финальный ответ без похода в LLM. Экономит время, деньги
    # и полностью убирает шанс на "фантомную" подписку из воздуха.
    if not clusters:
        try:
            await mes.delete()
        except Exception:
            pass
        await bot.send_rich_message(
            chat_id=message.chat.id,
            rich_message=types.InputRichMessage(
                markdown="Не нашел ни одну активную подписку!"
            )
        )
        return

    clusters_json = json.dumps(clusters, ensure_ascii=False, indent=2)

    with open('prompt.txt', 'r', encoding='utf-8') as f:
        prompt = f.read()

    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': clusters_json}
    ]

    logging.info("Clusters sent to LLM:\n%s", clusters_json)

    answer = await call_llm_with_retry(TextAI, messages, model='gpt-5.6-terra')

    if llm_failed(answer):
        logging.error(
            "LLM request failed after retries. error_text=%r, answer=%r",
            answer.error_text, answer.answer,
        )
        await mes.edit_text(
            "⚠️ Сервис обработки временно перегружен. "
            "Попробуйте отправить файл ещё раз через пару минут."
        )
        return

    try:
        await mes.delete()
    except Exception:
        pass

    answer_text = answer.answer
    logging.info("Answer:\n%s", answer_text)
    try:
        data = json.loads(answer_text)
    except json.JSONDecodeError as e:
        logging.error("JSON decode failed. Raw answer: %s", answer_text)
        return await message.answer(
            "⚠️ Не удалось обработать ответ сервиса. Попробуйте отправить файл ещё раз."
        )

    user_message = data['text']
    subs = data['subscriptions']

    names = [s['name'] for s in subs]
    cluster_indices = [s['cluster_index'] for s in subs]

    logging.info("Subs: %s, cluster_indices: %s", names, cluster_indices)

    statement_id = await save_statement(
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        records=records,
        names=names,
        clusters=clusters,
        cluster_indices=cluster_indices,
    )


    keyboard = make_subscriptions_keyboard(names, statement_id)

    try:
        await bot.send_rich_message(
            chat_id=message.chat.id,
            rich_message=types.InputRichMessage(
                markdown=user_message
            ),
            reply_markup=keyboard
        )
    except Exception:
        await bot.send_rich_message(
            chat_id=message.chat.id,
            rich_message=types.InputRichMessage(
                html=user_message
            ),
            reply_markup=keyboard
        )


@dp.message(F.text)
async def message_handler(message: types.Message):
    await bot.send_rich_message(chat_id=message.chat.id, rich_message=types.InputRichMessage(markdown="Отправьте файл формата .pdf для получения выписки!"))


@dp.callback_query(lambda c: c.data.startswith("sub:"))
async def on_subscription_click(callback_query: types.CallbackQuery):
    await callback_query.answer()

    try:
        _, statement_id_str, idx_str = callback_query.data.split(":", 2)
        statement_id = int(statement_id_str)
        idx = int(idx_str)
    except (ValueError, IndexError):
        await callback_query.message.answer("Ошибка: некорректные данные кнопки.")
        return

    statement = await get_statement(statement_id)
    if statement is None:
        await callback_query.message.answer(
            "Не удалось найти данные вашей выписки. Похоже, она устарела — пришлите PDF заново."
        )
        return

    names = statement['names']
    if idx < 0 or idx >= len(names):
        await callback_query.message.answer("Ошибка: подписка не найдена.")
        return

    subscription_name = names[idx]
    records = statement['records']

    # ── Достаём транзакции по явному индексу кластера, без угадывания ──
    clusters = statement.get('clusters') or []
    cluster_indices = statement.get('cluster_indices') or []

    matched_transactions = []
    cluster_period_type = None
    if idx < len(cluster_indices):
        real_cluster_idx = cluster_indices[idx]
        if 0 <= real_cluster_idx < len(clusters):
            periodicity = clusters[real_cluster_idx].get('periodicity') or {}
            cluster_period_type = periodicity.get('period_type')

    stats = compute_subscription_stats(matched_transactions, cluster_period_type)

    if stats is None:
        await callback_query.message.answer(
            f"⚠️ Не удалось посчитать статистику по «{subscription_name}» — "
            f"недостаточно данных в выписке."
        )
        return

    stats_card = render_stats_card(subscription_name, stats)

    processing_msg = await callback_query.message.answer(
        f"🔍 Готовлю письмо в поддержку «{subscription_name}»..."
    )

    with open('prompt_subscription.txt', 'r', encoding='utf-8') as f:
        prompt_template = f.read()

    prompt = prompt_template.replace("{SUBSCRIPTION_NAME}", subscription_name)

    # LLM теперь получает ТОЛЬКО задачу написать письмо — никаких чисел,
    # значит и ошибиться в арифметике негде.
    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': f"Напиши письмо для отмены подписки на {subscription_name}"},
    ]

    answer = await call_llm_with_retry(TextAI, messages, model='gpt-5.6-terra')

    try:
        await processing_msg.delete()
    except Exception:
        pass

    if llm_failed(answer):
        logging.error(
            "LLM request failed for subscription '%s'. error_text=%r, answer=%r",
            subscription_name, answer.error_text, answer.answer,
        )
        letter_text = "⚠️ Не удалось сгенерировать письмо. Попробуйте позже."
    else:
        letter_text = answer.answer.strip()

    final_message = (
        f"{stats_card}\n\n"
        f"✉️ **Письмо в поддержку {subscription_name}**\n\n"
        f"> {letter_text}"
    )

    try:
        await bot.send_rich_message(
            chat_id=callback_query.message.chat.id,
            rich_message=types.InputRichMessage(markdown=final_message)
        )
    except Exception:
        await bot.send_rich_message(
            chat_id=callback_query.message.chat.id,
            rich_message=types.InputRichMessage(html=final_message)
        )



@dp.shutdown()
async def on_shutdown():
    await close_pool()


if __name__ == '__main__':
    asyncio.run(main())
