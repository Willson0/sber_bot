# Словарь иконок для сервисов
SERVICE_ICONS = {
    'NETFLIX': '🎬',
    'SPOTIFY': '🎵',
    'YANDEX PLUS': '',
    'APPLE': '',
    'GOOGLE': '🔍',
    'KINOPOISK': '🎥',
    'IVI': '📺',
    'OKKO': '📡',
    'VK': '🔵',
    'TELEGRAM PREMIUM': '✈️',
    'YOUTUBE PREMIUM': '▶️',
    'ICLOUD': '☁️',
    'FITNESS': '🏋️',
    'AMAZON': '📦',
    'DISNEY': '🏰',
    'HBO': '🎭',
    'TIKTOK': '🎵',
}

# Иконки для категорий
CATEGORY_ICONS = {
    'Развлечения': '🎬',
    'Музыка': '🎵',
    'Спорт': '🏋️',
    'Подписки': '📱',
    'Облако': '☁️',
    'Обучение': '📚',
}


def get_service_icon(merchant_name: str) -> str:
    """
    Возвращает иконку для сервиса
    """
    merchant_upper = merchant_name.upper()

    for key, icon in SERVICE_ICONS.items():
        if key in merchant_upper or merchant_upper in key:
            return icon

    # Если не нашли, возвращаем стандартную
    return '💳'


def get_category_icon(category: str) -> str:
    """
    Возвращает иконку для категории
    """
    return CATEGORY_ICONS.get(category, '📦')