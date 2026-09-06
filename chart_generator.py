"""
Детерминированный расчёт статистики по подписке.
Никакой LLM — только Python, поэтому числа гарантированно точные
и совпадают с тем, что реально лежит в выписке.
"""
from datetime import datetime

PERIODS_PER_MONTH = {
    'weekly': 30 / 7,       # ~4.29 раза в месяц
    'monthly': 1,
    'quarterly': 1 / 3,
    'yearly': 1 / 12,
}


def _parse_date(d: str):
    try:
        return datetime.strptime(d, '%d.%m.%Y')
    except Exception:
        return None


def compute_subscription_stats(transactions: list[dict], period_type: str | None = None) -> dict | None:
    """
    Считает статистику по списаниям подписки.
    transactions — список dict с 'date' и 'amount'.
    period_type — 'monthly'/'weekly'/'quarterly'/'yearly' (из cluster['periodicity']),
                  если None — считаем как ежемесячную по умолчанию.
    """
    points = []
    for t in transactions:
        date = _parse_date(t.get('date', ''))
        amount = t.get('amount')
        if date is None or amount is None:
            continue
        points.append((date, abs(amount)))

    if not points:
        return None

    points.sort(key=lambda p: p[0])
    dates = [p[0] for p in points]
    amounts = [p[1] for p in points]

    count = len(points)
    avg_amount = sum(amounts) / count

    multiplier = PERIODS_PER_MONTH.get(period_type, 1)
    monthly_estimate = avg_amount * multiplier

    # Тренд: сравниваем среднее первой половины списаний со второй
    trend = 'stable'
    trend_pct = 0.0
    if count >= 4:
        mid = count // 2
        first_half_avg = sum(amounts[:mid]) / mid
        second_half_avg = sum(amounts[mid:]) / (count - mid)
        if first_half_avg > 0:
            trend_pct = round((second_half_avg - first_half_avg) / first_half_avg * 100, 1)
            if trend_pct > 5:
                trend = 'up'
            elif trend_pct < -5:
                trend = 'down'

    last_n = min(3, count)
    last_charges = [
        {'date': d.strftime('%d.%m.%Y'), 'amount': a}
        for d, a in zip(dates[-last_n:], amounts[-last_n:])
    ]
    last_charges.reverse()  # от самого свежего к старому

    return {
        'count': count,
        'first_date': dates[0].strftime('%d.%m.%Y'),
        'last_date': dates[-1].strftime('%d.%m.%Y'),
        'last_charges': last_charges,
        'avg_amount': round(avg_amount, 2),
        'monthly_estimate': round(monthly_estimate, 2),
        'total_6m': round(monthly_estimate * 6, 2),
        'total_12m': round(monthly_estimate * 12, 2),
        'trend': trend,
        'trend_pct': trend_pct,
    }


def render_stats_card(subscription_name: str, stats: dict) -> str:
    """Формирует красивый Markdown-блок из готовой статистики. Никакого LLM."""
    def fmt(v):
        return f"{v:,.0f}".replace(',', ' ')

    lines = [
        f"📊 **Статистика по подписке «{subscription_name}»**",
        "",
        f"Найдено списаний: **{stats['count']}**",
        f"Первое: {stats['first_date']} · Последнее: {stats['last_date']}",
        "",
        "**Последние списания:**",
    ]
    for ch in stats['last_charges']:
        lines.append(f"- {ch['date']} — {fmt(ch['amount'])} ₽")

    lines += [
        "",
        f"**Средний платёж:** {fmt(stats['avg_amount'])} ₽",
        f"**Прогноз за 6 месяцев:** {fmt(stats['total_6m'])} ₽",
        f"**Прогноз за год:** {fmt(stats['total_12m'])} ₽",
    ]

    if stats['trend'] == 'up':
        lines.append(f"\n📈 Цена подписки выросла на **{stats['trend_pct']}%** за период наблюдения.")
    elif stats['trend'] == 'down':
        lines.append(f"\n📉 Цена подписки снизилась на **{abs(stats['trend_pct'])}%** за период наблюдения.")

    return '\n'.join(lines)
