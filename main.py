import asyncio
from aiogram import Dispatcher, types, F
from bot import bot
import datetime
import io
import os
import logging
from integrations.hydraai import TextAI
import openpyxl
import pdfplumber
from aiogram.filters import Command
from utils import extract_system_subscriptions, make_subscriptions_keyboard

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

@dp.message(F.document)
async def pdf_handler(message: types.Message):
    document = message.document
    if not document.file_name.lower().endswith('.pdf'):
        await message.reply("Пожалуйста, отправьте файл формата .pdf")
        return

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
    pdf_text = ""
    with pdfplumber.open(file_content) as pdf:
      for page in pdf.pages:
          # Если страница содержит таблицу:
          tables = page.extract_tables()
          for table in tables:
              for row in table:
                  pdf_text += "\t".join(str(cell) for cell in row) + "\n"
          # Если нет таблиц, просто текст:
          if not tables:
              pdf_text += page.extract_text() or ""
    # except Exception as e:
    #     await message.reply(f"Ошибка чтения PDF: {e}")
    #     return

    # Читаем системный промпт
    with open('prompt.txt', 'r', encoding='utf-8') as f:
        prompt = f.read()

    # Логируем пдф-контент
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(
       filename='logs/pdf_extract.log',
       filemode='a',
       format='%(asctime)s | %(levelname)s | %(message)s',
       level=logging.INFO,
       encoding='utf-8'
    )
    logging.info("PDF text extracted:\n%s", pdf_text)

    # Собираем промпт для нейросети
    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': pdf_text}
    ]

    mes = await message.answer("Генерирую ответ по вашему PDF...")
    answer = await TextAI.from_text(messages=messages, model='gpt-5.6-terra')
    if answer.error_text:
        return await message.answer(f"ОШИБКА: {answer.error_text}")

    try:
        await mes.delete()
    except:
        pass

    user_text, subscriptions = extract_system_subscriptions(answer.answer)
    if subscriptions:
        keyboard = make_subscriptions_keyboard(subscriptions)
    else:
        keyboard = None

    try:
        await bot.send_rich_message(
            chat_id=message.chat.id,
            rich_message=types.InputRichMessage(
                markdown=user_text
            ),
            reply_markup=keyboard
        )
    except Exception:
        await bot.send_rich_message(
            chat_id=message.chat.id,
            rich_message=types.InputRichMessage(
                html=user_text
            ),
            reply_markup=keyboard
        )

@dp.message(F.text)
async def message_handler(message: types.Message):
    await bot.send_rich_message(chat_id=message.chat.id, rich_message=types.InputRichMessage(markdown="Отправьте файл формата .pdf для получения выписки!"))
    # messages = [
    #     {'role': 'system', 'content': 'Используй Latex формулы при необходимости (ОБЕРНУТЬ LATEX В $ или $$) и MarkDown'},
    #     {'role': 'user', 'content': message.html_text}
    # ]

    # mes = await message.answer("Генерирую ответ...")
    # answer = await TextAI.from_text(messages=messages, model='gpt-4o-mini')
    # if answer.error_text:
    #     return await message.answer(f"ОШИБКА: {answer.error_text}")

    # try: await mes.delete()
    # except: pass

    # try:
    #     await bot.send_rich_message(chat_id=message.chat.id, rich_message=types.InputRichMessage(markdown=answer.answer))
    # except:
    #     await bot.send_rich_message(chat_id=message.chat.id, rich_message=types.InputRichMessage(html=answer.answer))


@dp.shutdown()
async def on_shutdown():
    pass


if __name__ == '__main__':
    asyncio.run(main())
