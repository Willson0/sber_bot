import pandas as pd
import numpy as np
import re
import pdfplumber
from typing import List, Dict


class SubscriptionAnalyzer:
    def __init__(self):
        # Категории, которые НЕ являются подписками
        self.non_subscription_keywords = [
            'продукты', 'супермаркет', 'магазин', 'пятерочка', 'магнит', 'перекресток', 'вкусвилл',
            'азс', 'бензин', 'топливо', 'лукойл', 'роснефть', 'газпром',
            'кафе', 'ресторан', 'макдональдс', 'starbucks', 'кофе', 'бургер',
            'такси', 'uber', 'яндекс такси', 'ситимобил', 'драйв',
            'аптека', 'лекарства', 'здоровье', 'доктор',
            'перевод', 'сбербанк онлайн', 'тинькофф', 'альфа', 'втб',
            'банкомат', 'снятие наличных', 'cash', 'наличные',
            'жкх', 'коммунальные', 'электроэнергия', 'вода', 'газ', 'квартплата',
            'зарплата', 'пенсия', 'стипендия', 'возврат', 'cashback', 'кэшбэк', 'проценты'
        ]

        # Известные сервисы подписок
        self.known_services = {
            'NETFLIX': ['NETFLIX', 'NFLX', 'НЕТФЛИКС'],
            'SPOTIFY': ['SPOTIFY', 'СПОТИФАЙ'],
            'YANDEX PLUS': ['YANDEX PLUS', 'ЯНДЕКС ПЛЮС', 'YANDEX.PLUS'],
            'APPLE': ['APPLE.COM', 'APPLE MUSIC', 'ICLOUD', 'APP STORE', 'ITUNES'],
            'GOOGLE': ['GOOGLE', 'GOOGLE PLAY', 'YOUTUBE PREMIUM', 'GOOGLE ONE'],
            'KINOPOISK': ['KINOPOISK', 'КИНОПОИСК'],
            'IVI': ['IVI', 'ИВИ'],
            'OKKO': ['OKKO', 'ОККО'],
            'VK': ['VK', 'VKONTAKTE', 'ВКОНТАКТЕ', 'VK MUSIC'],
            'FITNESS': ['FITNESS', 'GYM', 'СПОРТЗАЛ', 'WORLD CLASS'],
            'TELEGRAM PREMIUM': ['TELEGRAM PREMIUM', 'TELEGRAM STARS'],
            'AMAZON': ['AMAZON', 'AMAZON PRIME', 'AMZN']
        }

    def normalize_merchant(self, name: str) -> str:
        """Нормализация названия сервиса"""
        if not name or pd.isna(name):
            return "Неизвестно"

        name = str(name).upper().strip()
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', ' ', name)

        for service, variants in self.known_services.items():
            for variant in variants:
                if variant in name:
                    return service

        return name

    def is_subscription_like(self, description: str) -> bool:
        """Проверяет, похоже ли описание на подписку"""
        desc_lower = description.lower()

        for keyword in self.non_subscription_keywords:
            if keyword in desc_lower:
                return False

        return True

    def parse_csv(self, file_path: str) -> pd.DataFrame:
        """Парсинг CSV файла с выпиской"""
        for encoding in ['utf-8', 'windows-1251', 'latin1']:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        df.columns = [col.lower().strip() for col in df.columns]

        col_map = {
            'date': ['date', 'дата', 'transaction_date', 'дата операции', 'дата платежа'],
            'amount': ['amount', 'сумма', 'transaction_amount', 'сумма операции', 'сумма платежа'],
            'description': ['description', 'описание', 'merchant', 'назначение', 'получатель',
                            'наименование', 'категория', 'описание операции']
        }

        final_cols = {}
        for std_name, variants in col_map.items():
            for variant in variants:
                if variant in df.columns:
                    final_cols[variant] = std_name
                    break

        df = df.rename(columns=final_cols)

        if 'date' not in df.columns or 'amount' not in df.columns:
            raise ValueError("Не найдены колонки 'Дата' и 'Сумма'. Проверьте формат CSV.")

        if 'description' not in df.columns:
            df['description'] = 'Транзакция'

        df['date'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=True, format='mixed')
        df = df.dropna(subset=['date'])

        df['amount'] = df['amount'].astype(str).str.replace(',', '.').str.replace(' ', '').str.replace('₽', '')
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').abs()
        df = df.dropna(subset=['amount'])

        df['normalized_merchant'] = df['description'].apply(self.normalize_merchant)
        df['is_sub_like'] = df['description'].apply(self.is_subscription_like)

        return df

    def parse_pdf(self, file_path: str) -> pd.DataFrame:
        """Попытка извлечь данные из PDF"""
        transactions = []

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')
                for line in lines:
                    match = re.search(r'(\d{2}[.\-/]\d{2}[.\-/]\d{2,4}).*?(\d[\d\s,]*[.,]?\d*)', line)
                    if match:
                        date_str = match.group(1).replace('/', '-').replace('.', '-')
                        amount_str = match.group(2).replace(' ', '').replace(',', '.')

                        try:
                            amount = abs(float(amount_str))
                            if amount > 10:
                                transactions.append({
                                    'date': date_str,
                                    'amount': amount,
                                    'description': line.strip()[:50]
                                })
                        except ValueError:
                            continue

        if not transactions:
            raise ValueError("Не удалось извлечь транзакции из PDF. Пожалуйста, используйте формат CSV.")

        df = pd.DataFrame(transactions)
        df['date'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=True, format='mixed')
        df = df.dropna(subset=['date', 'amount'])
        df['normalized_merchant'] = df['description'].apply(self.normalize_merchant)
        df['is_sub_like'] = df['description'].apply(self.is_subscription_like)

        return df

    def find_subscriptions(self, df: pd.DataFrame, min_occurrences: int = 2) -> List[Dict]:
        """Поиск подписок по повторяющимся платежам"""
        subscriptions = []

        # Фильтруем только те, что похожи на подписки
        df_filtered = df[df['is_sub_like'] == True]

        # Группируем по нормализованному названию
        grouped = df_filtered.groupby('normalized_merchant')

        for merchant, group in grouped:
            if len(group) < min_occurrences:
                continue

            group = group.sort_values('date')

            dates = group['date'].values
            amounts = group['amount'].values

            # Вычисляем интервалы между платежами
            intervals = []
            for i in range(1, len(dates)):
                days_diff = (pd.Timestamp(dates[i]) - pd.Timestamp(dates[i - 1])).days
                intervals.append(days_diff)

            if not intervals:
                continue

            avg_interval = np.mean(intervals)

            # Определяем тип подписки
            is_subscription = False
            frequency = None
            multiplier_monthly = 1
            multiplier_yearly = 12

            if 28 <= avg_interval <= 32:
                is_subscription = True
                frequency = 'monthly'
                multiplier_monthly = 1
                multiplier_yearly = 12
            elif 360 <= avg_interval <= 370:
                is_subscription = True
                frequency = 'yearly'
                multiplier_monthly = 1 / 12
                multiplier_yearly = 1
            elif 6 <= avg_interval <= 8:
                is_subscription = True
                frequency = 'weekly'
                multiplier_monthly = 4.33
                multiplier_yearly = 52

            if not is_subscription:
                continue

            # Проверяем стабильность сумм (допуск 15%)
            avg_amount = np.mean(amounts)
            std_amount = np.std(amounts)

            if len(amounts) > 2:
                coefficient_of_variation = std_amount / avg_amount
                if coefficient_of_variation > 0.15:
                    continue

            # Проверяем разброс
            min_amount = np.min(amounts)
            max_amount = np.max(amounts)

            if max_amount / min_amount > 1.3:
                continue

            # Собираем последние 3 платежа
            recent_payments = []
            last_3 = group.tail(3)
            for _, row in last_3.iterrows():
                recent_payments.append({
                    'date': row['date'].strftime('%d.%m.%Y'),
                    'amount': round(row['amount'], 2)
                })

            # Считаем сумму за последние 6 месяцев
            six_months_ago = df['date'].max() - pd.DateOffset(months=6)
            recent_group = group[group['date'] >= six_months_ago]
            total_6_months = recent_group['amount'].sum()

            monthly_amount = avg_amount * multiplier_monthly
            yearly_amount = avg_amount * multiplier_yearly

            subscription = {
                'merchant': merchant,
                'frequency': frequency,
                'monthly_amount': round(monthly_amount, 2),
                'yearly_amount': round(yearly_amount, 2),
                'total_6_months': round(total_6_months, 2),
                'transactions': len(group),
                'last_payment': group['date'].max().strftime('%Y-%m-%d'),
                'first_payment': group['date'].min().strftime('%Y-%m-%d'),
                'avg_amount': round(avg_amount, 2),
                'recent_payments': recent_payments
            }

            subscriptions.append(subscription)

        subscriptions.sort(key=lambda x: x['yearly_amount'], reverse=True)

        return subscriptions

    def analyze(self, file_path: str) -> Dict:
        """Полный анализ файла"""
        if file_path.lower().endswith('.pdf'):
            df = self.parse_pdf(file_path)
        else:
            df = self.parse_csv(file_path)

        subscriptions = self.find_subscriptions(df)

        total_monthly = sum(s['monthly_amount'] for s in subscriptions)
        total_yearly = sum(s['yearly_amount'] for s in subscriptions)

        return {
            'subscriptions': subscriptions,
            'total_monthly': round(total_monthly, 2),
            'total_yearly': round(total_yearly, 2),
            'count': len(subscriptions),
            'period': {
                'from': df['date'].min().strftime('%Y-%m-%d'),
                'to': df['date'].max().strftime('%Y-%m-%d')
            },
            'total_transactions': len(df),
            'total_amount': round(df['amount'].sum(), 2)
        }


def detect_free_trials(df: pd.DataFrame) -> list:
    """Обнаруживает бесплатные пробные периоды"""
    trials = []

    # Ищем платежи 0-10 рублей
    zero_payments = df[df['amount'].between(0, 10, inclusive='both')]

    if not zero_payments.empty:
        for _, row in zero_payments.iterrows():
            trials.append({
                'merchant': row.get('description', 'Unknown'),
                'amount': row['amount']
            })

    return trials