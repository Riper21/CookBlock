"""Слой БД: профиль, точечное редактирование, дневник, вес, избранное, чат.

Боевой nutrition_chef.db не затрагивается: conftest перенаправляет DB_PATH в tests/.
"""

import asyncio

import database

PROFILE = {
    "gender": "женский",
    "age": 28,
    "height": 168.0,
    "weight": 58.5,
    "activity": "умеренная активность",
    "goal": "мягкое снижение веса",
    "persons_count": 1,
    "allergies": "арахис, лактоза",
    "disliked_foods": "кинза, вареный лук, печень",
    "favorite_foods": "манго, пармезан, горький шоколад, авокадо",
    "cooking_habit": "на 2-3 дня вперёд (заготовки)",
    "meal_schedule": "завтрак 08:30, обед 13:30, ужин 19:00",
    "target_calories": 1550.0,
    "target_protein": 93.0,
    "target_fat": 58.5,
    "target_carbs": 163.0,
    "is_onboarded": 1,
}


def run(coro):
    return asyncio.run(coro)


def test_profile_roundtrip():
    run(database.init_db())
    run(database.save_user_profile(99900001, PROFILE))
    loaded = run(database.get_user_profile(99900001))
    assert loaded is not None
    assert loaded["gender"] == "женский"
    assert loaded["favorite_foods"] == PROFILE["favorite_foods"]
    assert "2-3" in loaded["cooking_habit"]
    assert loaded["allergies"] == "арахис, лактоза"


def test_partial_update_preserves_other_fields():
    """Инвариант AGENTS.md Правило 4: смена цели/веса не стирает остальные поля."""
    run(database.save_user_profile(99900002, PROFILE))
    run(database.update_profile_fields(99900002, {"goal": "поддержание формы", "target_calories": 1900.0}))
    loaded = run(database.get_user_profile(99900002))
    assert loaded["goal"] == "поддержание формы"
    assert loaded["target_calories"] == 1900.0
    assert loaded["favorite_foods"] == PROFILE["favorite_foods"]
    assert loaded["allergies"] == PROFILE["allergies"]
    assert loaded["disliked_foods"] == PROFILE["disliked_foods"]


def test_food_logs_summary_and_deletion():
    uid, date = 99900003, "2026-09-20"
    run(database.save_user_profile(uid, PROFILE))

    log1 = run(database.add_food_log(uid, "Завтрак", "Овсянка 50г, 2 яйца",
                                     420.0, 24.0, 14.0, 48.0, date))
    log2 = run(database.add_food_log(uid, "Обед", "Гречка, курица, салат",
                                     510.0, 42.0, 11.0, 58.0, date))
    assert log1 > 0 and log2 > 0

    logs = run(database.get_daily_food_logs(uid, date))
    assert len(logs) == 2 and logs[0]["meal_type"] == "Завтрак"

    summary = run(database.get_daily_summary(uid, date))
    assert summary["meals_count"] == 2
    assert summary["calories"] == 930.0
    assert summary["protein"] == 66.0

    assert run(database.delete_food_log(log1, uid)) is True
    after = run(database.get_daily_summary(uid, date))
    assert after["calories"] == 510.0

    run(database.clear_daily_food_logs(uid, date))
    assert run(database.get_daily_food_logs(uid, date)) == []


def test_weight_dynamics():
    uid = 99900004
    run(database.add_weight_entry(uid, 62.0, "Старт"))
    run(database.add_weight_entry(uid, 60.5, "Неделя 1"))
    dyn = run(database.get_weight_dynamics(uid))
    assert dyn["has_data"] is True
    assert dyn["count"] == 2
    assert round(dyn["total_diff"], 1) == -1.5


def test_favorites_lifecycle():
    uid = 99900005
    fav_id = run(database.add_favorite(uid, "kbzhu", "Расчет КБЖУ (обед)",
                                       "ИТОГО: 466 ккал"))
    assert fav_id > 0
    favs = run(database.get_favorites(uid))
    assert any(f["id"] == fav_id for f in favs)
    assert run(database.delete_favorite(fav_id, uid)) is True
    assert all(f["id"] != fav_id for f in run(database.get_favorites(uid)))


def test_chat_history_persistence_and_reset():
    uid = 99900006
    run(database.add_chat_message(uid, "user", "Что съесть на ужин?"))
    run(database.add_chat_message(uid, "assistant", "Легкий салат с курицей."))
    history = run(database.get_recent_chat_messages(uid, limit=8))
    assert len(history) == 2
    assert history[-1]["role"] == "assistant"
    run(database.clear_chat_messages(uid))
    assert run(database.get_recent_chat_messages(uid, limit=8)) == []
