import asyncio
from aiogram import Dispatcher, types, F
from bot import bot
import datetime
import io
from integrations.hydraai import TextAI
import openpyxl
import PyPDF2

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
    try:
        reader = PyPDF2.PdfReader(file_content)
        pdf_text = ""
        for page in reader.pages:
            pdf_text += page.extract_text() or ""
        if not pdf_text.strip():
            await message.reply("Не удалось извлечь текст из PDF-файла.")
            return
    except Exception as e:
        await message.reply(f"Ошибка чтения PDF: {e}")
        return

    # Собираем промпт для нейросети
    messages = [
        {'role': 'system', 'content': 'Используй Latex формулы при необходимости (ОБЕРНУТЬ LATEX В $ или $$) и MarkDown. Данные получены из PDF-файла.'},
        {'role': 'user', 'content': pdf_text}
    ]

    mes = await message.answer("Генерирую ответ по вашему PDF...")
    answer = await TextAI.from_text(messages=messages, model='gpt-4o-mini')
    if answer.error_text:
        return await message.answer(f"ОШИБКА: {answer.error_text}")

    try:
        await mes.delete()
    except:
        pass

    try:
        await bot.send_rich_message(chat_id=message.chat.id, rich_message=types.InputRichMessage(markdown=answer.answer))
    except:
        await bot.send_rich_message(chat_id=message.chat.id, rich_message=types.InputRichMessage(html=answer.answer))

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
