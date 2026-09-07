import os
import time
import pandas as pd
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from analyzer import SubscriptionAnalyzer
from chart_generator import create_pie_chart
from alternatives import get_alternatives
from icons import get_service_icon
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Максимальная длина сообщения в Telegram
MAX_MESSAGE_LENGTH = 4096


def get_savings_comparison(yearly_savings: float) -> str:
    """Возвращает мотивирующий текст в зависимости от суммы экономии"""
    if yearly_savings < 5000:
        return "🍕 Пару раз заказать еду в хороший ресторан или купить вкусный торт."
    elif yearly_savings < 15000:
        return "🎧 Новые беспроводные наушники или умную колонку с Алисой/Марусей."
    elif yearly_savings < 30000:
        return "⌚ Крутой фитнес-браслет, смарт-часы или билеты на короткие выходные у моря."
    elif yearly_savings < 60000:
        return "📱 Новый смартфон среднего класса или отличный игровой монитор."
    elif yearly_savings < 100000:
        return "📱 Флагманский smartphone (iPhone 15 / Samsung S24) или 💻 Хороший ноутбук!"
    else:
        return "✈️ Полноценное путешествие за границу, новый MacBook или первый взнос на автомобиль!"


def get_cancel_letter(merchant_name: str) -> str:
    """Генерирует персонализированное письмо для отмены подписки"""
    return (
        f"Здравствуйте! Прошу отменить мою подписку в сервисе "
        f"{merchant_name} и отключить дальнейшие регулярные списания "
        f"с моей карты. Пожалуйста, подтвердите отмену подписки. Спасибо!"
    )


def generate_excel_report(subscriptions: list, user_id: int) -> str:
    """
    Создаёт Excel-файл с отчётом по подпискам
    Возвращает путь к созданному файлу
    """
    if not subscriptions:
        return ""

    data = []
    for i, sub in enumerate(subscriptions, 1):
        # Получаем лучшую (самую дешёвую) альтернативу
        alts = get_alternatives(sub['merchant'], sub['avg_amount'])
        best_alt = alts[0]['name'] if alts else "Нет более дешёвых аналогов"

        # Считаем потенциальную экономию
        savings = (sub['avg_amount'] - alts[0]['price']) * 12 if alts else 0

        data.append({
            '№': i,
            'Сервис': sub['merchant'],
            'Сумма в месяц (₽)': sub['avg_amount'],
            'Сумма в год (₽)': sub['yearly_amount'],
            'Первый платеж': sub['first_payment'],
            'Последний платеж': sub['last_payment'],
            'Кол-во списаний': sub['transactions'],
            'Дешёвая альтернатива': best_alt,
            'Экономия в год (₽)': round(savings, 2)
        })

    # Создаём DataFrame и сохраняем в Excel
    df = pd.DataFrame(data)
    filename = f"report_{user_id}_{int(time.time())}.xlsx"

    # Используем openpyxl для сохранения
    df.to_excel(filename, index=False, engine='openpyxl')

    return filename


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - приветствие пользователя"""
    await update.message.reply_text(
        "👋 *Привет! Я — Сканер Подписок.*\n\n"
        "Отправь мне выписку из банка в формате *.csv* или *.pdf*, и я:\n"
        "1. Найду все скрытые подписки\n"
        "2. Посчитаю, сколько ты тратишь в месяц и год\n"
        "3. Покажу, на что можно потратить эти деньги 🎁\n"
        "4. Подготовлю письма для отмены ✉️\n"
        "5. Построю круговую диаграмму 📊\n"
        "6. Предложу более дешёвые альтернативы 🔄\n"
        "7. Найду бесплатные пробные периоды ⚠️\n"
        "8. *Сформирую удобный Excel-отчёт* 📥\n\n"
        "Весь текстовый отчёт придёт *одним сообщением* для удобства!",
        parse_mode=ParseMode.MARKDOWN
    )


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list:
    """Разбивает длинное сообщение на части"""
    if len(text) <= max_length:
        return [text]

    parts = []
    while len(text) > max_length:
        split_pos = text.rfind('\n\n', 0, max_length)
        if split_pos == -1:
            split_pos = max_length

        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip()

    if text:
        parts.append(text)

    return parts


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загруженного CSV/PDF файла"""
    document = update.message.document
    if not document:
        return

    file_name = document.file_name.lower()
    if not (file_name.endswith('.csv') or file_name.endswith('.pdf')):
        await update.message.reply_text(
            "❌ Пожалуйста, отправь файл в формате *.csv* или *.pdf*."
        )
        return

    status_msg = await update.message.reply_text("⏳ Загружаю и анализирую файл... Это может занять несколько секунд.")

    try:
        file = await context.bot.get_file(document.file_id, read_timeout=60)
        file_path = f"temp_{update.message.from_user.id}_{file_name}"
        await file.download_to_drive(file_path, read_timeout=60)

        analyzer = SubscriptionAnalyzer()
        result = analyzer.analyze(file_path)

        # === Проверка на бесплатные пробные периоды ===
        free_trials = []
        try:
            if file_path.lower().endswith('.csv'):
                temp_df = pd.read_csv(file_path, encoding='utf-8')
                temp_df.columns = [col.lower().strip() for col in temp_df.columns]

                amount_col = None
                for col in ['amount', 'сумма', 'сумма операции']:
                    if col in temp_df.columns:
                        amount_col = col
                        break

                if amount_col:
                    temp_df[amount_col] = temp_df[amount_col].astype(str).str.replace(',', '.').str.replace(' ',
                                                                                                            '').str.replace(
                        '₽', '')
                    temp_df[amount_col] = pd.to_numeric(temp_df[amount_col], errors='coerce')

                    zero_payments = temp_df[temp_df[amount_col].between(0, 10, inclusive='both')]

                    if not zero_payments.empty:
                        for _, row in zero_payments.iterrows():
                            desc_col = next(
                                (col for col in ['description', 'описание', 'наименование', 'описание операции'] if
                                 col in temp_df.columns), None)
                            if desc_col and row[desc_col]:
                                free_trials.append({
                                    'merchant': str(row[desc_col])[:50],
                                    'amount': row[amount_col]
                                })
        except Exception as e:
            print(f"⚠️ Не удалось проверить пробные периоды: {e}")
            free_trials = []
        # ================================================

        if result['count'] == 0:
            report = (
                "📊 *Результаты анализа:*\n\n"
                f"📅 Период: {result['period']['from']} — {result['period']['to']}\n"
                f"💳 Всего транзакций: {result['total_transactions']}\n\n"
                "✅ *Подписки не найдены!*\n\n"
                "💡 *Совет:* Для максимально точного анализа используйте формат *.csv*."
            )
            await status_msg.edit_text(report, parse_mode=ParseMode.MARKDOWN)
        else:
            # === Собираем текстовый отчёт ===
            comparison_text = get_savings_comparison(result['total_yearly'])

            full_report = (
                f"📊 *РЕЗУЛЬТАТЫ АНАЛИЗА ПОДПИСОК*\n\n"
                f"📅 Период: {result['period']['from']} — {result['period']['to']}\n"
                f"💳 Проанализировано транзакций: {result['total_transactions']}\n"
                f"💰 Общая сумма всех трат: {result['total_amount']:,.2f} ₽\n\n"
                f"🚨 *Найдено активных подписок:* {result['count']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💸 *Итого в месяц:* {result['total_monthly']:,.2f} ₽\n"
                f"💸 *Итого в год:* {result['total_yearly']:,.2f} ₽\n\n"
                f"💡 *ЕСЛИ ВЫ ОТКАЖЕТЕСЬ ОТ ВСЕХ ПОДПИСОК, ТО СЭКОНОМИТЕ {result['total_yearly']:,.0f} ₽ ЗА ГОД!*\n\n"
                f"🎁 *На эти деньги можно купить:*\n{comparison_text}\n\n"
            )

            if free_trials:
                full_report += "⚠️ *НАЙДЕНЫ БЕСПЛАТНЫЕ ПРОБНЫЕ ПЕРИОДЫ:*\n\n"
                for trial in free_trials:
                    full_report += f"• {get_service_icon(trial['merchant'])} {trial['merchant']} — {trial['amount']} ₽\n"
                full_report += "\n_Внимание: через несколько дней с вас могут списать полную стоимость!_\n\n"
                full_report += "━━━━━━━━━━━━━━━━━━━━\n\n"

            for i, sub in enumerate(result['subscriptions'][:10], 1):
                icon = get_service_icon(sub['merchant'])

                payments_list = ""
                for p in sub['recent_payments']:
                    payments_list += f"   • {p['date']} — {p['amount']:,.2f} ₽\n"

                cancel_letter = get_cancel_letter(sub['merchant'])

                full_report += (
                    f"*{i}. {icon} {sub['merchant']}*\n"
                    f"   💳 {sub['avg_amount']:,.2f} ₽/мес ({sub['yearly_amount']:,.2f} ₽/год)\n"
                    f"   📅 Последние списания:\n{payments_list}"
                    f"   ✉️ Письмо для отмены:\n"
                    f"   _{cancel_letter}_\n\n"
                )

                alternatives = get_alternatives(sub['merchant'], sub['avg_amount'])
                if alternatives:
                    full_report += f"   🔄 *Альтернативы:*\n"
                    for alt in alternatives[:2]:
                        full_report += f"   • {alt['name']} — {alt['price']} ₽/мес ({alt['desc']})\n"
                    full_report += "\n"

                full_report += "━━━━━━━━━━━━━━━━━━━━\n\n"

            full_report += (
                "💡 *Совет:* Скопируйте письмо выше и отправьте в поддержку, или отключите подписку в настройках.\n\n"
                "📩 Отправьте новый файл, чтобы проанализировать другую выписку!"
            )

            # === 1. Отправляем график ===
            if result['subscriptions']:
                try:
                    chart_file = create_pie_chart(result['subscriptions'], result['total_yearly'])
                    if chart_file and os.path.exists(chart_file):
                        await update.message.reply_photo(
                            photo=open(chart_file, 'rb'),
                            caption="📊 *Распределение расходов по подпискам*",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        os.remove(chart_file)
                except Exception as e:
                    print(f"⚠️ Ошибка при создании графика: {e}")

            # === 2. Отправляем Excel-файл ===
            try:
                excel_filename = generate_excel_report(result['subscriptions'], update.message.from_user.id)
                if excel_filename and os.path.exists(excel_filename):
                    with open(excel_filename, 'rb') as f:
                        await update.message.reply_document(
                            document=f,
                            filename="Отчет_по_подпискам.xlsx",
                            caption="📥 *Полный отчёт в формате Excel*\n\nЗдесь удобная таблица со всеми найденными подписками, датами платежей и альтернативами для экономии.",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    os.remove(excel_filename)  # Удаляем временный файл
            except Exception as e:
                print(f"⚠️ Ошибка при создании Excel: {e}")

            # === 3. Отправляем текстовый отчёт ===
            message_parts = split_message(full_report)
            for i, part in enumerate(message_parts):
                if i == 0:
                    await status_msg.edit_text(part, parse_mode=ParseMode.MARKDOWN)
                else:
                    await update.message.reply_text(part, parse_mode=ParseMode.MARKDOWN)

        # Очистка временного файла выписки
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        print(f"Ошибка при обработке файла: {e}")
        error_msg = f"❌ *Ошибка при анализе:*\n\n`{str(e)}`\n\n💡 Убедитесь, что это корректная выписка из банка."
        try:
            await status_msg.edit_text(error_msg, parse_mode=ParseMode.MARKDOWN)
        except:
            await update.message.reply_text(error_msg, parse_mode=ParseMode.MARKDOWN)
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)


async def error_handler(update: object, context) -> None:
    """Обрабатывает ошибки в боте"""
    print(f"Update {update} вызвал ошибку: {context.error}")
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("⚠️ Произошла ошибка при обработке. Попробуйте ещё раз.")
        except:
            pass


def main():
    """Запуск бота с авто-переподключением"""
    if not BOT_TOKEN:
        print("❌ ОШИБКА: Токен не найден в файле .env!")
        return

    print("🤖 Запускаю бота...")

    try:
        request = HTTPXRequest(
            connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30
        )

        app = Application.builder() \
            .token(BOT_TOKEN) \
            .request(request) \
            .get_updates_request(HTTPXRequest(read_timeout=60, connect_timeout=30)) \
            .build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
        app.add_error_handler(error_handler)

        print("✅ БОТ УСПЕШНО ЗАПУЩЕН!")
        print("📱 Открой Telegram и отправь боту команду /start или файл выписки.")
        print("⏹️ Для остановки нажми Ctrl+C")
        print("🔄 Бот автоматически переподключится при обрыве связи\n")

        while True:
            try:
                app.run_polling(allowed_updates=Update.ALL_TYPES)
            except Exception as e:
                print(f"\n⚠️ Потеряно соединение: {e}")
                print("🔄 Переподключение через 5 секунд...")
                time.sleep(5)

    except ImportError:
        print("❌ Библиотека PySocks не установлена! Установи: pip install PySocks")
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")


if __name__ == '__main__':
    main()