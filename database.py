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
                    clusters_json LONGTEXT,
                    cluster_indices_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)

            # ── Миграция для уже существующей таблицы (если бот
            # запускался раньше без этих колонок) — без этого блока
            # у "старых" установок init_db не добавит новые столбцы
            # сам, т.к. CREATE TABLE IF NOT EXISTS их не трогает.
            await _add_column_if_missing(cur, 'clusters_json', 'LONGTEXT')
            await _add_column_if_missing(cur, 'cluster_indices_json', 'TEXT')


async def _add_column_if_missing(cur, column: str, coltype: str):
    await cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'statements' AND COLUMN_NAME = %s
        """,
        (DB_NAME, column),
    )
    (count,) = await cur.fetchone()
    if count == 0:
        await cur.execute(f"ALTER TABLE statements ADD COLUMN {column} {coltype}")


async def save_statement(user_id, chat_id, records, names, clusters=None, cluster_indices=None) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO statements
                    (user_id, chat_id, transactions_json, names_json, clusters_json, cluster_indices_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    chat_id,
                    json.dumps(records, ensure_ascii=False),
                    json.dumps(names, ensure_ascii=False),
                    json.dumps(clusters or [], ensure_ascii=False),
                    json.dumps(cluster_indices or [], ensure_ascii=False),
                ),
            )
            return cur.lastrowid


async def get_statement(statement_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM statements WHERE id = %s", (statement_id,))
            row = await cur.fetchone()
            if row is None:
                return None

            row['records'] = json.loads(row['transactions_json'])
            row['names'] = json.loads(row['names_json'])
            row['clusters'] = json.loads(row['clusters_json']) if row['clusters_json'] else []
            row['cluster_indices'] = json.loads(row['cluster_indices_json']) if row['cluster_indices_json'] else []
            return row


async def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
