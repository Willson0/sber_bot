import re
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# def extract_system_subscriptions(answer_text):
#     """
#     Извлекает список подписок из строки system: ... в конце ответа.
#     Возвращает (чистый_текст_для_пользователя, массив_подписок)
#     """
#     # regex для поиска system: ... в конце строки (может быть с \n)
#     match = re.search(r"(?:\n|^)system:\s*(.*)$", answer_text.strip())
#     if match:
#         subs_line = match.group(1).strip()
#         subs_list = [s.strip() for s in subs_line.split(",") if s.strip()]
#         # Удаляем system: ... из текста для пользователя
#         clean_text = re.sub(r"(?:\n|^)system:.*$", "", answer_text.strip()).strip()
#     else:
#         subs_list = []
#         clean_text = answer_text
#     return clean_text, subs_list


def make_subscriptions_keyboard(subscriptions):
    keyboard = []
    # разбиваем список по 2 в строке
    for i in range(0, len(subscriptions), 2):
        row = [
            InlineKeyboardButton(
                text=sub,
                callback_data=f"subscription:{sub}"
            ) for sub in subscriptions[i:i+2]
        ]
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton(
            text="Открыть аналитику",
            web_app=WebAppInfo(url="https://your-webapp-url.com/")
        )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)