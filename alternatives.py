# База данных подписок и их альтернатив
SUBSCRIPTION_ALTERNATIVES = {
    'NETFLIX': {
        'name': 'Netflix',
        'avg_price': 399,
        'alternatives': [
            {'name': 'Иви', 'price': 299, 'desc': 'Российский сервис с фильмами и сериалами'},
            {'name': 'Okko', 'price': 249, 'desc': 'Кино и сериалы, есть спорт'},
            {'name': 'Кинопоиск', 'price': 229, 'desc': 'От Яндекса, много контента'},
            {'name': 'Premier', 'price': 199, 'desc': 'Сериалы от ТНТ и СТС'}
        ]
    },
    'APPLE': {
        'name': 'Apple Services',
        'avg_price': 199,
        'alternatives': [
            {'name': 'Яндекс Музыка', 'price': 199, 'desc': 'Музыка + подкасты'},
            {'name': 'VK Музыка', 'price': 149, 'desc': 'Дешевле, большая библиотека'},
            {'name': 'Spotify', 'price': 199, 'desc': 'Международный сервис'}
        ]
    },
    'SPOTIFY': {
        'name': 'Spotify',
        'avg_price': 199,
        'alternatives': [
            {'name': 'Яндекс Музыка', 'price': 199, 'desc': 'Аналогичный функционал'},
            {'name': 'VK Музыка', 'price': 149, 'desc': 'Дешевле на 50₽/мес'},
            {'name': 'Apple Music', 'price': 199, 'desc': 'От Apple'}
        ]
    },
    'YANDEX PLUS': {
        'name': 'Яндекс Плюс',
        'avg_price': 299,
        'alternatives': [
            {'name': 'Плюс Мульти', 'price': 499, 'desc': 'Яндекс Плюс + Кинопоиск + Музыка'},
            {'name': 'Иви + Музыка', 'price': 399, 'desc': 'Комбо от Иви'}
        ]
    },
    'KINOPOISK': {
        'name': 'Кинопоиск',
        'avg_price': 229,
        'alternatives': [
            {'name': 'Иви', 'price': 299, 'desc': 'Больше контента'},
            {'name': 'Okko', 'price': 249, 'desc': 'Есть спорт и премьеры'},
            {'name': 'Premier', 'price': 199, 'desc': 'Дешевле, сериалы ТНТ'}
        ]
    },
    'IVI': {
        'name': 'Иви',
        'avg_price': 299,
        'alternatives': [
            {'name': 'Кинопоиск', 'price': 229, 'desc': 'Дешевле на 70₽/мес'},
            {'name': 'Okko', 'price': 249, 'desc': 'Есть спорт'},
            {'name': 'Premier', 'price': 199, 'desc': 'Самый дешёвый вариант'}
        ]
    },
    'OKKO': {
        'name': 'Okko',
        'avg_price': 249,
        'alternatives': [
            {'name': 'Кинопоиск', 'price': 229, 'desc': 'Дешевле на 20₽/мес'},
            {'name': 'Premier', 'price': 199, 'desc': 'Дешевле на 50₽/мес'}
        ]
    },
    'TELEGRAM PREMIUM': {
        'name': 'Telegram Premium',
        'avg_price': 299,
        'alternatives': [
            {'name': 'Бесплатный Telegram', 'price': 0, 'desc': 'Можно обойтись без премиума'}
        ]
    },
    'YOUTUBE PREMIUM': {
        'name': 'YouTube Premium',
        'avg_price': 199,
        'alternatives': [
            {'name': 'YouTube с рекламой', 'price': 0, 'desc': 'Бесплатно, но с рекламой'},
            {'name': 'YouTube Music', 'price': 199, 'desc': 'Только музыка без рекламы'}
        ]
    },
    'ICLOUD': {
        'name': 'iCloud',
        'avg_price': 199,
        'alternatives': [
            {'name': 'Яндекс Диск', 'price': 149, 'desc': '100 ГБ за 149₽/мес'},
            {'name': 'Google Drive', 'price': 199, 'desc': '100 ГБ, аналогично'},
            {'name': 'Облако Mail.ru', 'price': 149, 'desc': 'Дешевле на 50₽/мес'}
        ]
    },
    'FITNESS': {
        'name': 'Фитнес-клуб',
        'avg_price': 3500,
        'alternatives': [
            {'name': 'Домашние тренировки', 'price': 0, 'desc': 'YouTube, бесплатные приложения'},
            {'name': 'Онлайн фитнес', 'price': 999, 'desc': 'Тренировки дома с тренером'},
            {'name': 'Бюджетный зал', 'price': 1500, 'desc': 'Простые залы без доп.услуг'}
        ]
    },
    'AMAZON': {
        'name': 'Amazon Prime',
        'avg_price': 500,
        'alternatives': [
            {'name': 'Кинопоиск', 'price': 229, 'desc': 'Дешевле, русский контент'},
            {'name': 'Иви', 'price': 299, 'desc': 'Российский сервис'}
        ]
    }
}


def get_alternatives(merchant_name: str, current_price: float) -> list:
    """
    Возвращает список альтернатив для подписки
    """
    # Ищем подписку в базе
    for key, data in SUBSCRIPTION_ALTERNATIVES.items():
        if key in merchant_name.upper() or merchant_name.upper() in key:
            # Фильтруем только те альтернативы, что дешевле
            cheaper_alternatives = [
                alt for alt in data['alternatives']
                if alt['price'] < current_price
            ]
            # Сортируем по цене (сначала самые дешёвые)
            cheaper_alternatives.sort(key=lambda x: x['price'])
            return cheaper_alternatives

    return []


def calculate_savings(subscription, alternative) -> dict:
    """
    Считает экономию при переходе на альтернативу
    """
    monthly_savings = subscription['avg_amount'] - alternative['price']
    yearly_savings = monthly_savings * 12

    return {
        'monthly': round(monthly_savings, 2),
        'yearly': round(yearly_savings, 2)
    }


def format_alternative_message(merchant_name: str, current_price: float, alternative: dict) -> str:
    """
    Форматирует сообщение об альтернативе
    """
    savings = calculate_savings(
        {'avg_amount': current_price},
        alternative
    )

    return (
        f"💡 *{alternative['name']}* — {alternative['price']} ₽/мес\n"
        f"   {alternative['desc']}\n"
        f"   💰 *Экономия:* {savings['monthly']} ₽/мес ({savings['yearly']} ₽/год)"
    )