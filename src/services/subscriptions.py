import aiosqlite
import datetime
from pathlib import Path

async def init_db(db_path: str):
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS subscribers (
            chat_id INTEGER PRIMARY KEY,
            created_at TEXT
        )
        """
        )
        await db.commit()

async def add_subscriber(db_path: str, chat_id: int):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO subscribers (chat_id, created_at) VALUES (?, ?)",
            (chat_id, datetime.datetime.now(datetime.timezone.utc).isoformat()),
        )
        await db.commit()

async def remove_subscriber(db_path: str, chat_id: int):
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM subscribers WHERE chat_id = ?", (chat_id,))
        await db.commit()

async def list_subscribers(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT chat_id FROM subscribers") as cur:
            rows = await cur.fetchall()
            return [row[0] for row in rows]
