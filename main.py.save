import asyncio
from aiogram import Dispatcher, types, F
from bot import bot
import datetime
import io
import os
import re
import logging
from integrations.hydraai import TextAI
import openpyxl
import pdfplumber
from aiogram.filters import Command
import json
from utils import make_subscriptions_keyboard, parse_statement

dp = Dispatcher()

async def main():
    cmds = [
        types.BotCommand(command="start", description="Главное меню"),
    ]
    await bot.set_my_commands(commands=cmds)
    await dp.start_polling(bot, allowed_updates=["message", 'callback_query'])

@dp.startup()
async def startup():
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
    
    # Гарантируем BytesIO
    if isinstance(file_bytes, bytes):
        file_content = io.BytesIO(file_bytes)
    else:
        # если это file-like объект, перематываем и используем напрямую
        file_bytes.seek(0)
        file_content = file_bytes


    # Читаем PDF и превращаем в текст
    try:
        bank, records = parse_statement(file_content)
    except Exception as e:
        await mes.edit_text(f"Ошибка чтения PDF: {e}")
        return

    if not records:
        await mes.edit_text("Не удалось извлечь транзакции из PDF.")
        return

    records = [clean_record(r) for r in records]
    transactions_json = json.dumps(records, ensure_ascii=False, indent=2)

    content = f"{transactions_json}"

    # Читаем системный промпт
    with open('prompt.txt', 'r', encoding='utf-8') as f:
        prompt = f.read()

    # Логируем
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(
       filename='logs/pdf_extract.log',
       filemode='a',
       format='%(asctime)s | %(levelname)s | %(message)s',
       level=logging.INFO,
       encoding='utf-8'
    )

    # Собираем промпт для нейросети
    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': content}
    ]

    logging.info("PDF TEXT:\n%s", transactions_json)

    answer = await TextAI.from_text(messages=messages, model='gpt-5.6-terra')
    if answer.error_text:
        return await message.answer(f"ОШИБКА: {answer.error_text}")

    try:
        await mes.delete()
    except:
        pass

    answer = answer.answer
    logging.info("Answer:\n%s", answer)
    try:
        data = json.loads(answer)
    except json.JSONDecodeError as e:
        return await message.answer(f"Ошибка разбора JSON: {e}")

    user_message = data['text']
    # user_message = data['hi'] + "\n\n"
    # for sub in data['subs']:
    #     user_message += sub['text'] + "\n"
    # user_message += "\n" + data['end']


    logging.info("Subs:\n%s", data['names'])

    keyboard = make_subscriptions_keyboard(data['names'])

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

@dp.callback_query(lambda c: c.data.startswith("subscription:"))
async def on_subscription_click(callback_query: types.CallbackQuery):
    subscription_name = callback_query.data.split(":", 1)[1]
    await callback_query.answer()

    await bot.send_rich_message(chat_id=callback_query.message.chat.id, rich_message=types.InputRichMessage(html=f"""
        Вы выбрали {subscription_name}:
        Начинаю полную обработку..."""
    ))



@dp.shutdown()
async def on_shutdown():
    pass


if __name__ == '__main__':
    asyncio.run(main())
