import os
import json
import aiomysql

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'subscriptions_bot')

_pool: aiomysql.Pool | None = None


async def _ensure_database_exists():
    """Подключается без указания конкретной БД и создаёт её, если нет."""
    conn = await aiomysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True,
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        conn.close()


async def get_pool() -> aiomysql.Pool:
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
            autocommit=True,
            minsize=1,
            maxsize=10,
        )
    return _pool


async def init_db():
    """Создаёт базу (если нет) и таблицу при старте бота."""
    await _ensure_database_exists()
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS statements (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    transactions_json LONGTEXT NOT NULL,
                    names_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)


async def save_statement(user_id: int, chat_id: int, records: list, names: list) -> int:
    pool = await get_pool()
    transactions_json = json.dumps(records, ensure_ascii=False)
    names_json = json.dumps(names, ensure_ascii=False)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO statements (user_id, chat_id, transactions_json, names_json) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, chat_id, transactions_json, names_json),
            )
            return cur.lastrowid


async def get_statement(statement_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM statements WHERE id = %s", (statement_id,))
            row = await cur.fetchone()
            if row:
                row['records'] = json.loads(row['transactions_json'])
                row['names'] = json.loads(row['names_json'])
            return row


async def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
