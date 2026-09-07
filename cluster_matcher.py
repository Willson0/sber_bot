"""
Восстановление cluster_index для подписок, НЕ доверяя индексу от LLM.

Проблема: модель возвращает {"name": "...", "cluster_index": N}, но N она
проставляет ненадёжно — на длинных массивах кластеров индекс «съезжает»
(наблюдали: "Премьер" получил индекс 10 вместо 11 и подтянул чужой кластер).

Решение: сопоставляем человекочитаемое имя подписки с кластерами
детерминированным кодом по representative_name. Индекс от LLM используем
только как последний fallback.

Стратегия (от точного к нечёткому):
  1. Точное вхождение нормализованного имени в normalize_name(representative_name).
  2. Fuzzy-сходство (та же метрика, что в проекте) выше порога.
  3. Fallback: индекс, который дала LLM (если он валиден).
Один кластер не может быть назначен двум подпискам (защита от коллизий).
"""
import logging

from subscription_finder import normalize_name, _similarity

# Порог для нечёткого сопоставления имени с representative_name.
# Ниже, чем NAME_SIMILARITY_THRESHOLD (0.80) для транзакций: здесь мы
# сравниваем короткое бренд-имя с длинным representative_name, так что
# точное вхождение обычно решает, а fuzzy — подстраховка.
MATCH_THRESHOLD = 0.55


def _cluster_rep(cluster: dict) -> str:
    return normalize_name(cluster.get("representative_name", ""))


def _best_cluster_for(name: str, clusters: list, taken: set) -> int | None:
    norm = normalize_name(name)
    if not norm:
        return None

    # Уровень 1: точное вхождение (в обе стороны — имя в rep или rep в имя).
    exact = []
    for i, cl in enumerate(clusters):
        if i in taken:
            continue
        rep = _cluster_rep(cl)
        if not rep:
            continue
        if norm in rep or rep in norm:
            exact.append(i)
    if len(exact) == 1:
        return exact[0]
    # Если точных несколько — среди них выбираем самый похожий по similarity.
    if len(exact) > 1:
        return max(exact, key=lambda i: _similarity(norm, _cluster_rep(clusters[i])))

    # Уровень 2: fuzzy по всем свободным кластерам.
    best_i, best_score = None, 0.0
    for i, cl in enumerate(clusters):
        if i in taken:
            continue
        score = _similarity(norm, _cluster_rep(cl))
        if score > best_score:
            best_i, best_score = i, score
    if best_i is not None and best_score >= MATCH_THRESHOLD:
        return best_i

    return None


def recover_cluster_indices(subs: list[dict], clusters: list[dict]) -> list[int]:
    """
    subs — список от LLM: [{"name": str, "cluster_index": int (ненадёжен)}, ...]
    clusters — массив кластеров, отданный LLM на вход (source of truth).

    Возвращает список индексов, по одному на каждую подписку из subs,
    в том же порядке. Индекс от LLM используется только как fallback.
    """
    taken: set = set()
    result: list[int] = []

    for s in subs:
        name = s.get("name", "")
        llm_idx = s.get("cluster_index")

        found = _best_cluster_for(name, clusters, taken)

        if found is not None:
            if found != llm_idx:
                logging.info(
                    "cluster_index recovered: '%s' LLM=%s -> matched=%s (rep=%r)",
                    name, llm_idx, found,
                    clusters[found].get("representative_name"),
                )
            result.append(found)
            taken.add(found)
            continue

        # Fallback: доверяем индексу LLM, если он валиден и ещё не занят.
        if isinstance(llm_idx, int) and 0 <= llm_idx < len(clusters) and llm_idx not in taken:
            logging.warning(
                "cluster_index not matched by name for '%s', falling back to LLM idx=%s",
                name, llm_idx,
            )
            result.append(llm_idx)
            taken.add(llm_idx)
        else:
            logging.error(
                "cluster_index unresolved for '%s' (LLM idx=%s invalid/taken)",
                name, llm_idx,
            )
            result.append(-1)  # явный маркер «не найдено», аналитика упадёт на fallback

    return result
