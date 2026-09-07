"""
Проверка подлинности Telegram Mini App initData.

Telegram передаёт в Mini App строку initData (query-string). Её нужно
проверять по алгоритму из офиц. документации, иначе любой сможет
подделать user_id / statement_id и открыть чужую выписку.

Алгоритм:
  1. Разбираем initData как query-string в dict.
  2. Забираем поле hash отдельно, остальные пары сортируем по ключу.
  3. data_check_string = "key=value\n..." (без hash).
  4. secret_key = HMAC-SHA256(key="WebAppData", msg=BOT_TOKEN)
  5. calc_hash = HMAC-SHA256(key=secret_key, msg=data_check_string)  (hex)
  6. calc_hash должен совпасть с hash из initData.
  7. Дополнительно проверяем auth_date (защита от старых перехваченных строк).
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InitDataError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict:
    """
    Возвращает распарсенный и провалидированный payload (dict с полями Telegram,
    где 'user' уже распарсен из JSON). Бросает InitDataError при любой проблеме.
    """
    if not init_data:
        raise InitDataError("empty init_data")

    # parse_qsl сохраняет порядок, но нам он не важен — мы всё равно сортируем.
    pairs = dict(parse_qsl(init_data, strict_parsing=True))

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("no hash in init_data")

    data_check_string = "\n".join(
        f"{k}={pairs[k]}" for k in sorted(pairs.keys())
    )

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        raise InitDataError("hash mismatch")

    # Защита от переигрывания старой перехваченной строки.
    auth_date = pairs.get("auth_date")
    if auth_date is not None:
        try:
            if time.time() - int(auth_date) > max_age_seconds:
                raise InitDataError("init_data expired")
        except ValueError:
            raise InitDataError("bad auth_date")

    # Разворачиваем user (Telegram кладёт его как JSON-строку).
    if "user" in pairs:
        try:
            pairs["user"] = json.loads(pairs["user"])
        except json.JSONDecodeError:
            raise InitDataError("bad user json")

    return pairs
