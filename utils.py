import re
from aiogram.types import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
import pdfplumber
import json
import io

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


# def make_subscriptions_keyboard(subscriptions: list[str], statement_id:id):
#     keyboard = []
#     # разбиваем список по 2 в строке
#     for i in range(0, len(subscriptions), 2):
#         row = [
#             InlineKeyboardButton(
#                 text=sub,
#                 callback_data=f"sub:{statement_id}:{idx}"
#             ) for sub in subscriptions[i:i+2]
#         ]
#         keyboard.append(row)

#     keyboard.append([
#         InlineKeyboardButton(
#             text="Открыть аналитику",
#             web_app=WebAppInfo(url="https://your-webapp-url.com/")
#         )])
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)

WEBAPP_URL = "https://later.com"

def make_subscriptions_keyboard(names: list[str], statement_id: int):
    builder = InlineKeyboardBuilder()

    for idx, name in enumerate(names):
        # компактный callback_data: sub:<id_выписки>:<индекс_подписки>
        builder.button(text=name, callback_data=f"sub:{statement_id}:{idx}")

    # Кнопка веб-аппа — отдельная, не участвует в раскладке "по 2 в строке"
    builder.button(
        text="📊 Открыть полную аналитику",
        web_app=WebAppInfo(url=WEBAPP_URL),
    )

    # Раскладка: сначала N кнопок подписок по 2 в строке,
    # последняя кнопка (веб-апп) — отдельной строкой на всю ширину.
    if names:
        rows = [2] * (len(names) // 2)
        if len(names) % 2:
            rows.append(1)
        rows.append(1)  # строка под кнопку веб-аппа
        builder.adjust(*rows)
    else:
        builder.adjust(1)

    return builder.as_markup()

TIME_RE = re.compile(r'^\d{2}:\d{2}$')
DATE_RE = re.compile(r'^\d{2}\.\d{2}\.\d{4}$')

JUNK = ('Продолжение', 'Выписка по', 'ДАТА', 'Дата обработки', 'КАТЕГОРИЯ',
        'Для проверки', 'ПАО Сбербанк', 'Денежные средства', 'В выписке')


# ============ ПАРСЕР Т-БАНКА ============

def tbank_parse(file_obj, max_pages=None):
    """
    file_obj — путь к файлу (str) ИЛИ file-like объект (BytesIO).
    """
    records = []
    current = None

    with pdfplumber.open(file_obj) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        for page in pages:
            words = page.extract_words()

            lines = {}
            for w in words:
                key = round(w['top'] / 4)
                lines.setdefault(key, []).append(w)

            for key in sorted(lines):
                row = sorted(lines[key], key=lambda w: w['x0'])
                first_x = row[0]['x0']

                spis_date, amount_parts, desc_parts = None, [], []
                for w in row:
                    x, t = w['x0'], w['text']
                    if 120 <= x < 190:
                        spis_date = spis_date or t
                    elif 190 <= x < 290:
                        if t != '₽':
                            amount_parts.append(t)
                    elif x >= 385:
                        desc_parts.append(t)

                is_new = 50 <= first_x < 70 and DATE_RE.match(row[0]['text']) and amount_parts

                if is_new:
                    if current:
                        records.append(current)
                    amount = ''.join(amount_parts).replace('\u00a0', '')
                    current = {
                        'date': spis_date,
                        'amount': amount,
                        'desc': ' '.join(desc_parts),
                    }
                elif current and desc_parts:
                    tail = [w['text'] for w in row if w['x0'] >= 385]
                    current['desc'] += ' ' + ' '.join(tail)

    if current:
        records.append(current)
    return records


# ============ ПАРСЕР СБЕРА ============

def group_lines(page):
    lines = {}
    for w in page.extract_words():
        key = round(w['top'] / 4)
        lines.setdefault(key, []).append(w)
    return [sorted(lines[k], key=lambda w: w['x0']) for k in sorted(lines)]


def col(row, lo, hi):
    return [w['text'] for w in row if lo <= w['x0'] < hi]


def sber_parse(file_obj, max_pages=None):
    """
    file_obj — путь к файлу (str) ИЛИ file-like объект (BytesIO).
    """
    records = []
    current = None

    with pdfplumber.open(file_obj) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        for page in pages:
            for row in group_lines(page):
                if not row:
                    continue
                text_joined = ' '.join(w['text'] for w in row)
                if any(j in text_joined for j in JUNK):
                    continue

                first = row[0]['text']
                second = row[1]['text'] if len(row) > 1 else ''

                # СТРОКА А: дата операции + время (ЧЧ:ММ) → новая операция
                if DATE_RE.match(first) and TIME_RE.match(second):
                    if current:
                        records.append(current)
                    amount_parts = col(row, 420, 475)
                    amount = ''.join(amount_parts).replace('\u00a0', '').replace(' ', '')
                    sign = '+' if amount.startswith('+') else '-'
                    amount_num = amount.lstrip('+')
                    category = ' '.join(col(row, 150, 300))
                    current = {
                        'date': first,
                        'time': second,
                        'category': category,
                        'amount': amount_num,
                        'sign': sign,
                        'desc': '',
                    }

                # СТРОКА Б: дата обработки + код авторизации (6 цифр без ':') → мерчант
                elif current and DATE_RE.match(first) and second.isdigit() and len(second) == 6:
                    current['desc'] = ' '.join(col(row, 150, 360))

                # хвост описания — приклеиваем, номер карты пропускаем
                elif current and col(row, 150, 360):
                    tail = ' '.join(col(row, 150, 360))
                    if '****' not in tail:
                        current['desc'] += ' ' + tail

    if current:
        records.append(current)
    return records


# ============ ДИСПЕТЧЕР: ОПРЕДЕЛЕНИЕ БАНКА И ВЫЗОВ НУЖНОГО ПАРСЕРА ============

def detect_bank(file_obj) -> str:
    """
    Читает первую страницу PDF и определяет банк по ключевым словам.
    Возвращает 'sber', 'tbank' или 'unknown'.
    """
    with pdfplumber.open(file_obj) as pdf:
        first_page_text = pdf.pages[0].extract_text() or ""

    text_lower = first_page_text.lower()

    if 'сбер' in text_lower:
        return 'sber'
    if 'тбанк' in text_lower or 'т-банк' in text_lower:
        return 'tbank'

    return 'unknown'


def parse_statement(file_obj, max_pages=None):
    """
    Главная функция: определяет банк и вызывает нужный парсер.
    file_obj — file-like объект (BytesIO). Важно: после detect_bank
    нужно перематывать поток, т.к. pdfplumber "прочитывает" его.
    """
    # Определяем банк
    bank = detect_bank(file_obj)

    # Перематываем файл в начало перед основным парсингом
    file_obj.seek(0)

    if bank == 'sber':
        records = sber_parse(file_obj, max_pages=max_pages)
    elif bank == 'tbank':
        records = tbank_parse(file_obj, max_pages=max_pages)
    else:
        raise ValueError("Не удалось определить банк по содержимому PDF")

    return bank, records
