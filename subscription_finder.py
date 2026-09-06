"""
Детерминированная предобработка транзакций: находит потенциальные
подписки алгоритмически, ДО передачи в LLM.

LLM больше не ищет совпадения в сотнях строк — она получает готовые
кластеры и только (а) подтверждает/отклоняет их как подписку,
(б) генерирует текст письма и оформление по шаблону.
"""
import re
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher

try:
    from rapidfuzz import fuzz

    def _similarity(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return fuzz.token_sort_ratio(a, b) / 100.0
except ImportError:
    def _similarity(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()


SUBSCRIPTION_MARKERS = [
    'SBSCR', 'SUBSCR', 'SUBSCRIPTION', 'SUBS',
    'ПОДПИСКА', 'ПОДПИСК', 'RECURRING', 'РЕКУРРЕНТ',
    'AUTOPAY', 'АВТОПЛАТЕЖ', 'АВТОСПИСАНИЕ',
]

EXCLUDE_KEYWORDS = [
    'супермаркет', 'продукты', 'пятерочка', 'перекрест', 'магнит',
    'ашан', 'лента', 'вкусвилл', 'дикси',
    'такси', 'yandex go', 'ситимобил', 'gett', 'uber', 'убер',
    'азс', 'бензин', 'газпромнефть', 'лукойл', 'роснефть',
    'аптека', 'здравсити', 'ригла', 'горздрав',
    'ресторан', 'кафе', 'пицц', 'суши', 'фастфуд', 'кофе',
    'доставка еды', 'delivery club',
    'перевод', 'p2p', 'между своими', 'card2card', 'с2с',
    'снятие наличных', 'выдача наличных', 'atm', 'cash withdrawal',
    'заказ', 'одежда', 'обувь',
    'связной', 'мвидео', 'эльдорадо', 'dns',
]

MIN_SUBSCRIPTION_AMOUNT = 50.0
NAME_SIMILARITY_THRESHOLD = 0.80
AMOUNT_RATIO_THRESHOLD = 0.5  # суммы не должны отличаться больше чем в 2 раза


def has_marker(desc: str) -> bool:
    upper = (desc or '').upper()
    return any(m in upper for m in SUBSCRIPTION_MARKERS)


def is_excluded(record: dict) -> bool:
    text = f"{record.get('category', '')} {record.get('desc', '')}".lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def normalize_name(desc: str) -> str:
    text = (desc or '').upper()
    for marker in SUBSCRIPTION_MARKERS:
        text = text.replace(marker, ' ')
    text = re.sub(r'\*+\d*', ' ', text)        # маскированные номера карт ****1234
    text = re.sub(r'\d{4,}', ' ', text)         # длинные цифровые ID/чеки/даты
    text = re.sub(r'[^A-ZА-Я0-9\s]', ' ', text)  # пунктуация
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _parse_date(d: str) -> datetime:
    try:
        return datetime.strptime(d, '%d.%m.%Y')
    except Exception:
        return datetime.min


def cluster_transactions(records: list[dict]) -> list[dict]:
    """
    Возвращает список кластеров-кандидатов на подписку.
    Каждый кластер уже прошёл фильтры (сумма, исключения, похожесть),
    LLM'у остаётся только финальная классификация и оформление текста.
    """
    candidates = []
    for r in records:
        amount = r.get('amount')
        if amount is None or amount >= 0:
            continue
        if abs(amount) < MIN_SUBSCRIPTION_AMOUNT:
            continue
        if is_excluded(r):
            continue
        candidates.append(r)

    n = len(candidates)
    normalized = [normalize_name(r.get('desc', '')) for r in candidates]

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            if not normalized[i] or not normalized[j]:
                continue
            if _similarity(normalized[i], normalized[j]) < NAME_SIMILARITY_THRESHOLD:
                continue

            amt_i, amt_j = abs(candidates[i]['amount']), abs(candidates[j]['amount'])
            if min(amt_i, amt_j) / max(amt_i, amt_j) < AMOUNT_RATIO_THRESHOLD:
                continue

            union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    clusters = []
    for idxs in groups.values():
        txs = [candidates[i] for i in idxs]
        marker_flag = any(has_marker(t.get('desc', '')) for t in txs)

        # ключевое правило: либо ≥2 повтора, либо явный маркер подписки
        if len(txs) < 2 and not marker_flag:
            continue

        txs_sorted = sorted(txs, key=lambda t: _parse_date(t.get('date', '')))
        representative = Counter(t.get('desc', '') for t in txs).most_common(1)[0][0]

        clusters.append({
            'representative_name': representative,
            'has_subscription_marker': marker_flag,
            'occurrences': len(txs),
            'transactions': [
                {
                    'date': t.get('date'),
                    'amount': t.get('amount'),
                    'desc': t.get('desc'),
                    'category': t.get('category', ''),
                }
                for t in txs_sorted
            ],
        })

    # самые "убедительные" кластеры (больше повторов) — первыми, это помогает
    # LLM в случае урезания контекста не терять важные подписки
    clusters.sort(key=lambda c: c['occurrences'], reverse=True)
    return clusters


def build_llm_payload(records: list[dict]) -> list[dict]:
    """Точка входа для main.py"""
    return cluster_transactions(records)
