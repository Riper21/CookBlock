"""
Модуль асинхронной работы с базой данных SQLite через aiosqlite.
Хранит профили пользователей, рассчитанные нормы КБЖУ, Избранное,
историю сообщений и Дневник питания (Daily Food Log).
"""

import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import DB_PATH


async def init_db():
    """Инициализация таблиц базы данных и выполнение миграций."""
    # Родительская папка могла быть переопределена через DB_PATH (тесты, Docker)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Таблица профилей пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                gender TEXT DEFAULT 'женский',
                age INTEGER DEFAULT 30,
                height REAL DEFAULT 165.0,
                weight REAL DEFAULT 60.0,
                activity TEXT DEFAULT 'умеренная',
                goal TEXT DEFAULT 'поддержание',
                persons_count INTEGER DEFAULT 1,
                allergies TEXT DEFAULT '',
                disliked_foods TEXT DEFAULT '',
                favorite_foods TEXT DEFAULT '',
                cooking_habit TEXT DEFAULT 'каждый день свежее',
                meal_schedule TEXT DEFAULT '',
                target_calories REAL DEFAULT 1800.0,
                target_protein REAL DEFAULT 90.0,
                target_fat REAL DEFAULT 60.0,
                target_carbs REAL DEFAULT 220.0,
                is_onboarded INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Миграция: добавление новых колонок в существующую таблицу users при необходимости
        async with db.execute("PRAGMA table_info(users)") as cursor:
            existing_cols = {row[1] for row in await cursor.fetchall()}
            if "favorite_foods" not in existing_cols:
                await db.execute("ALTER TABLE users ADD COLUMN favorite_foods TEXT DEFAULT ''")
            if "cooking_habit" not in existing_cols:
                await db.execute("ALTER TABLE users ADD COLUMN cooking_habit TEXT DEFAULT 'каждый день свежее'")
            if "meal_schedule" not in existing_cols:
                await db.execute("ALTER TABLE users ADD COLUMN meal_schedule TEXT DEFAULT ''")

        # 2. Таблица избранного (меню, рецепты, расчеты КБЖУ)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,  -- 'menu', 'daymenu', 'recipe', 'kbzhu', 'general'
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # 3. Таблица постоянной истории диалогов (сохраняется даже при перезапуске бота)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,      -- 'user', 'assistant'
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id, id)
        """)

        # 4. Таблица Дневника питания (подсчет съеденного за день)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_food_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                log_date TEXT NOT NULL,       -- 'YYYY-MM-DD'
                meal_type TEXT NOT NULL,      -- 'Завтрак', 'Обед', 'Ужин', 'Перекус'
                food_description TEXT NOT NULL,
                calories REAL NOT NULL,
                protein REAL NOT NULL,
                fat REAL NOT NULL,
                carbs REAL NOT NULL,
                created_at TEXT NOT NULL,      -- 'HH:MM'
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_food_logs_user_date ON daily_food_logs(user_id, log_date)
        """)

        # 5. Таблица истории взвешиваний (еженедельный трекер веса)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weight_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                weight REAL NOT NULL,
                log_date TEXT NOT NULL,        -- 'YYYY-MM-DD'
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,      -- 'YYYY-MM-DD HH:MM:SS'
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_weight_history_user ON weight_history(user_id, log_date)
        """)

        await db.commit()


# ==================== РАБОТА С ПРОФИЛЕМ ПОЛЬЗОВАТЕЛЯ ====================

async def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """Получение профиля пользователя по user_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def save_user_profile(user_id: int, data: Dict[str, Any]) -> None:
    """Создание или полное обновление профиля пользователя."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (
                user_id, gender, age, height, weight, activity, goal,
                persons_count, allergies, disliked_foods, favorite_foods,
                cooking_habit, meal_schedule,
                target_calories, target_protein, target_fat, target_carbs,
                is_onboarded, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                gender = excluded.gender,
                age = excluded.age,
                height = excluded.height,
                weight = excluded.weight,
                activity = excluded.activity,
                goal = excluded.goal,
                persons_count = excluded.persons_count,
                allergies = excluded.allergies,
                disliked_foods = excluded.disliked_foods,
                favorite_foods = excluded.favorite_foods,
                cooking_habit = excluded.cooking_habit,
                meal_schedule = excluded.meal_schedule,
                target_calories = excluded.target_calories,
                target_protein = excluded.target_protein,
                target_fat = excluded.target_fat,
                target_carbs = excluded.target_carbs,
                is_onboarded = excluded.is_onboarded,
                updated_at = excluded.updated_at
        """, (
            user_id,
            data.get("gender", "женский"),
            data.get("age", 30),
            data.get("height", 165.0),
            data.get("weight", 60.0),
            data.get("activity", "умеренная"),
            data.get("goal", "поддержание"),
            data.get("persons_count", 1),
            data.get("allergies", ""),
            data.get("disliked_foods", ""),
            data.get("favorite_foods", ""),
            data.get("cooking_habit", "каждый день свежее"),
            data.get("meal_schedule", ""),
            data.get("target_calories", 1800.0),
            data.get("target_protein", 90.0),
            data.get("target_fat", 60.0),
            data.get("target_carbs", 220.0),
            data.get("is_onboarded", 1),
            data.get("created_at", now_str),
            now_str
        ))
        await db.commit()


VALID_USER_COLUMNS = {
    "gender", "age", "height", "weight", "activity", "goal",
    "persons_count", "allergies", "disliked_foods", "favorite_foods",
    "cooking_habit", "meal_schedule", "target_calories", "target_protein",
    "target_fat", "target_carbs", "is_onboarded"
}


async def update_profile_fields(user_id: int, updates: Dict[str, Any]) -> None:
    """Частичное обновление полей профиля с фильтрацией допустимых колонок."""
    if not updates:
        return
    filtered_updates = {k: v for k, v in updates.items() if k in VALID_USER_COLUMNS}
    if not filtered_updates:
        return
    filtered_updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    keys = list(filtered_updates.keys())
    set_clause = ", ".join([f"{k} = ?" for k in keys])
    values = [filtered_updates[k] for k in keys] + [user_id]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        await db.commit()


# ==================== ДНЕВНИК ПИТАНИЯ (DAILY FOOD LOG) ====================

async def add_food_log(
    user_id: int,
    meal_type: str,
    food_description: str,
    calories: float,
    protein: float,
    fat: float,
    carbs: float,
    log_date: Optional[str] = None
) -> int:
    """Добавление приема пищи в дневник за указанную дату (по умолчанию сегодня)."""
    if not log_date:
        log_date = datetime.now().strftime("%Y-%m-%d")
    created_at = datetime.now().strftime("%H:%M")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO daily_food_logs (
                user_id, log_date, meal_type, food_description,
                calories, protein, fat, carbs, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            log_date,
            meal_type,
            food_description,
            round(calories, 1),
            round(protein, 1),
            round(fat, 1),
            round(carbs, 1),
            created_at
        ))
        log_id = cursor.lastrowid
        await db.commit()
        return log_id


async def get_daily_food_logs(user_id: int, log_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получение всех записей дневника пользователя за определенную дату."""
    if not log_date:
        log_date = datetime.now().strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM daily_food_logs
            WHERE user_id = ? AND log_date = ?
            ORDER BY id ASC
        """, (user_id, log_date)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_daily_summary(user_id: int, log_date: Optional[str] = None) -> Dict[str, Any]:
    """Подсчет суммарных калорий и БЖУ за дату."""
    if not log_date:
        log_date = datetime.now().strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT 
                COALESCE(SUM(calories), 0.0) as total_cals,
                COALESCE(SUM(protein), 0.0) as total_prot,
                COALESCE(SUM(fat), 0.0) as total_fat,
                COALESCE(SUM(carbs), 0.0) as total_carbs,
                COUNT(id) as meals_count
            FROM daily_food_logs
            WHERE user_id = ? AND log_date = ?
        """, (user_id, log_date)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "calories": round(row[0], 1),
                    "protein": round(row[1], 1),
                    "fat": round(row[2], 1),
                    "carbs": round(row[3], 1),
                    "meals_count": int(row[4])
                }
            return {
                "calories": 0.0,
                "protein": 0.0,
                "fat": 0.0,
                "carbs": 0.0,
                "meals_count": 0
            }


async def delete_food_log(log_id: int, user_id: int) -> bool:
    """Удаление отдельной записи из дневника питания."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM daily_food_logs WHERE id = ? AND user_id = ?",
            (log_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def clear_daily_food_logs(user_id: int, log_date: Optional[str] = None) -> bool:
    """Полная очистка записей дневника за указанный день."""
    if not log_date:
        log_date = datetime.now().strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM daily_food_logs WHERE user_id = ? AND log_date = ?",
            (user_id, log_date)
        )
        await db.commit()
        return cursor.rowcount > 0


# ==================== РАБОТА С ИЗБРАННЫМ ====================

async def add_favorite(user_id: int, category: str, title: str, content: str) -> int:
    """Добавление записи в избранное. Возвращает id созданной записи."""
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO favorites (user_id, category, title, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, category, title, content, now_str))
        fav_id = cursor.lastrowid
        await db.commit()
        return fav_id


async def get_favorites(user_id: int, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получение всех избранных записей пользователя (или по категории)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if category:
            query = "SELECT * FROM favorites WHERE user_id = ? AND category = ? ORDER BY id DESC"
            params = (user_id, category)
        else:
            query = "SELECT * FROM favorites WHERE user_id = ? ORDER BY id DESC"
            params = (user_id,)
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_favorite_by_id(fav_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Получение избранной записи по id с проверкой владельца."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM favorites WHERE id = ? AND user_id = ?", (fav_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def delete_favorite(fav_id: int, user_id: int) -> bool:
    """Удаление записи из избранного."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM favorites WHERE id = ? AND user_id = ?", (fav_id, user_id))
        await db.commit()
        return cursor.rowcount > 0


# ==================== РАБОТА С ИСТОРИЕЙ ДИАЛОГА ====================

async def add_chat_message(user_id: int, role: str, content: str) -> None:
    """Сохранение реплики в постоянную историю (БД SQLite)."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO chat_messages (user_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, role, content, now_str))
        await db.commit()


async def get_recent_chat_messages(user_id: int, limit: int = 10) -> List[Dict[str, str]]:
    """Получение последних реплик пользователя для передачи в LLM."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT role, content FROM (
                SELECT id, role, content FROM chat_messages
                WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
        """, (user_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]


async def clear_chat_messages(user_id: int) -> None:
    """Очистка истории диалога для пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
        await db.commit()


# ==================== РАБОТА С ИСТОРИЕЙ ВЕСА (ТРЕКЕР ДИНАМИКИ) ====================

async def add_weight_entry(user_id: int, weight: float, notes: str = "") -> int:
    """Запись веса в историю взвешиваний."""
    now_dt = datetime.now()
    log_date = now_dt.strftime("%Y-%m-%d")
    created_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO weight_history (user_id, weight, log_date, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, float(weight), log_date, notes, created_at))
        await db.commit()
        return cursor.lastrowid


async def get_weight_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Получение последних записей веса пользователя (от новых к старым)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM weight_history
            WHERE user_id = ?
            ORDER BY log_date DESC, id DESC
            LIMIT ?
        """, (user_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_weight_dynamics(user_id: int) -> Dict[str, Any]:
    """Расчет динамики изменения веса: начальный, текущий, общий отвес."""
    history = await get_weight_history(user_id, limit=30)
    if not history:
        return {"has_data": False}

    current = history[0]["weight"]
    oldest = history[-1]["weight"]
    diff = current - oldest
    prev = history[1]["weight"] if len(history) > 1 else current
    prev_diff = current - prev

    return {
        "has_data": True,
        "current_weight": current,
        "start_weight": oldest,
        "total_diff": diff,
        "prev_diff": prev_diff,
        "count": len(history),
        "history": history
    }

