"""
Сборка данных для веб-аналитики из сохранённой ботом выписки.

Переиспользует существующие модули проекта:
  - subscription_finder.find_matching_transactions — находит все списания
    конкретного сервиса по всей выписке (та же логика, что и в боте);
  - chart_generator.compute_subscription_stats — считает агрегаты
    (средний платёж, прогнозы, тренд) — числа гарантированно совпадают
    с тем, что бот показывает в Telegram.

Ничего не пересчитывает своим кодом — только раскладывает уже
посчитанное в форму, удобную для графиков на фронте.
"""
from datetime import datetime

from subscription_finder import find_matching_transactions
from chart_generator import compute_subscription_stats


def _parse_date(d: str):
    try:
        return datetime.strptime(d, "%d.%m.%Y")
    except Exception:
        return None


def _period_type_for(name: str, records: list, clusters: list, cluster_indices: list):
    """
    Пытаемся вытащить period_type ('monthly'/'yearly'/...) из сохранённых
    кластеров, чтобы прогнозы считались с правильным множителем.
    Если не нашли — вернём None (chart_generator тогда возьмёт monthly=1).
    """
    for ci in cluster_indices:
        if 0 <= ci < len(clusters):
            per = clusters[ci].get("periodicity") or {}
            if per.get("period_type"):
                return per["period_type"]
    return None


def _transactions_for(name_idx, name, records, clusters, cluster_indices):
    """
    Основной источник списаний подписки — сохранённый кластер, который LLM
    сопоставила этой подписке (cluster_indices[name_idx] -> clusters[...]).
    Это надёжнее повторного fuzzy-матчинга по имени: не теряем транзакции
    из-за расхождения «Netflix» vs «NETFLIX.COM».

    Fallback на find_matching_transactions — только если кластер почему-то
    недоступен (старые записи в БД без clusters).
    """
    if name_idx < len(cluster_indices):
        ci = cluster_indices[name_idx]
        if 0 <= ci < len(clusters):
            txs = clusters[ci].get("transactions") or []
            if txs:
                return txs
    return find_matching_transactions(records, name)


def build_analytics(statement: dict) -> dict:
    """
    statement — строка из БД, уже с распарсенными records/names/clusters
    (см. database.get_statement).
    Возвращает JSON-совместимый dict для фронта.
    """
    records = statement.get("records", []) or []
    names = statement.get("names", []) or []
    clusters = statement.get("clusters", []) or []
    cluster_indices = statement.get("cluster_indices", []) or []

    subscriptions = []
    total_monthly = 0.0
    total_12m = 0.0

    for name_idx, name in enumerate(names):
        matched = _transactions_for(name_idx, name, records, clusters, cluster_indices)
        period_type = _period_type_for(name, records, clusters, cluster_indices)
        stats = compute_subscription_stats(matched, period_type)
        if stats is None:
            continue

        history = [
            {"date": t.get("date"), "amount": abs(t.get("amount") or 0)}
            for t in matched
            if _parse_date(t.get("date", ""))
        ]

        total_monthly += stats["monthly_estimate"]
        total_12m += stats["total_12m"]

        subscriptions.append({
            "name": name,
            "count": stats["count"],
            "first_date": stats["first_date"],
            "last_date": stats["last_date"],
            "avg_amount": stats["avg_amount"],
            "monthly_estimate": stats["monthly_estimate"],
            "total_12m": stats["total_12m"],
            "trend": stats["trend"],
            "trend_pct": stats["trend_pct"],
            "period_type": period_type or "monthly",
            "history": history,
        })

    # Сортируем по годовым тратам — самые дорогие подписки первыми.
    subscriptions.sort(key=lambda s: s["total_12m"], reverse=True)

    # Помесячные суммарные траты по всем подпискам (для линейного графика).
    monthly_map = {}  # 'YYYY-MM' -> сумма
    for sub in subscriptions:
        for h in sub["history"]:
            dt = _parse_date(h["date"])
            if dt:
                key = dt.strftime("%Y-%m")
                monthly_map[key] = monthly_map.get(key, 0.0) + h["amount"]
    monthly_timeline = [
        {"month": k, "amount": round(v, 2)}
        for k, v in sorted(monthly_map.items())
    ]

    return {
        "summary": {
            "subscriptions_count": len(subscriptions),
            "total_monthly": round(total_monthly, 2),
            "total_12m": round(total_12m, 2),
            "transactions_count": len(records),
        },
        "subscriptions": subscriptions,
        "monthly_timeline": monthly_timeline,
    }
