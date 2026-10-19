"""
Общие фикстуры тестов «Пищеблока».

Герметичность (0 сети, 0 токенов, боевая БД не трогается):
- ключи-заглушки выставляются в окружение ДО импорта config:
  load_dotenv не перекрывает уже существующие переменные, поэтому
  реальные ключи из .env (если он есть на машине разработчика)
  в тесты не попадают и наружу не уходят;
- DB_PATH перенаправляется на файл внутри tests/ (в .gitignore через *.db).
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:" + "aA0_" * 10)
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-fake-key")
os.environ["DB_PATH"] = str(ROOT / "tests" / "_test_nutrition_chef.db")

import aiosqlite  # noqa: E402
import database  # noqa: E402

TEST_TABLES = (
    "users",
    "daily_food_logs",
    "weight_history",
    "favorites",
    "chat_messages",
)


async def _init_and_wipe():
    await database.init_db()
    async with aiosqlite.connect(database.DB_PATH) as db:
        for table in TEST_TABLES:
            await db.execute(f"DELETE FROM {table}")
        await db.commit()


def _cleanup_db_file():
    for suffix in ("", "-journal", "-wal", "-shm"):
        p = Path(str(database.DB_PATH) + suffix)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


def pytest_sessionfinish(session, exitstatus):
    _cleanup_db_file()
