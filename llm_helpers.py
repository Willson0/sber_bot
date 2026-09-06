"""
Вспомогательные функции для устойчивой работы с LLM-провайдером.
Ловит ситуации, когда провайдер (Codex/OpenAI-совместимый бэкенд)
возвращает текстовое сообщение об ошибке ВМЕСТО валидного ответа,
и это сообщение не попадает в answer.error_text.
"""
import asyncio
import logging
import re

# Все известные варианты текста ошибок от Codex-прослойки.
# Дополняйте список по мере появления новых формулировок в логах.
CODEX_ERROR_PATTERNS = [
    r'\[?Codex\s+error:',
    r'servers?\s+are\s+currently\s+overloaded',
    r'An error occurred while processing your request',
    r'rate limit',
    r'internal server error',
    r'please try again later',
    r'help\.openai\.com',
]

_CODEX_ERROR_RE = re.compile('|'.join(CODEX_ERROR_PATTERNS), re.IGNORECASE)


def is_codex_error(text: str | None) -> bool:
    """True, если текст ответа похож на служебную ошибку провайдера,
    а не на реальный полезный ответ модели."""
    if not text or not text.strip():
        return True
    return bool(_CODEX_ERROR_RE.search(text))


async def call_llm_with_retry(
    text_ai_cls,
    messages: list[dict],
    model: str = 'gpt-5.6-terra',
    retries: int = 2,
    base_delay: float = 2.0,
):
    """
    Вызывает TextAI.from_text с автоматическими повторами при сбоях
    провайдера (перегрузка серверов, rate limit и т.д.).
    Возвращает последний ответ (answer) — успешный или неудачный.
    """
    last_answer = None

    for attempt in range(retries + 1):
        answer = await text_ai_cls.from_text(messages=messages, model=model)
        last_answer = answer

        has_error = bool(answer.error_text) or is_codex_error(answer.answer)
        if not has_error:
            return answer

        logging.warning(
            "LLM attempt %d/%d failed. error_text=%r, answer_preview=%r",
            attempt + 1, retries + 1,
            answer.error_text,
            (answer.answer or '')[:200],
        )

        if attempt < retries:
            await asyncio.sleep(base_delay * (attempt + 1))  # 2с, 4с, 6с...

    return last_answer


def llm_failed(answer) -> bool:
    """Единая проверка: считать ли ответ LLM неудачным."""
    return bool(answer.error_text) or is_codex_error(answer.answer)
