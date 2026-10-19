"""
Автономный тестовый раннер на базе локального дата-сета.
Работает 100% оффлайн:
- Без обращений к внешним API (OpenAI / DeepSeek).
- С нулевым расходом токенов и баланса.
- Проверяет локальное распознавание речи (faster-whisper).
- Проверяет расчеты КБЖУ, прогресс-бары, SQLite базу данных и динамику веса.
"""

import os
import json
import sys
import asyncio
from datetime import datetime

# Настройка UTF-8 для консоли Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import database
import nutrition


async def test_whisper_offline():
    print("\n--- ТЕСТ 1: Локальное распознавание речи (faster-whisper) ---")
    audio_path = os.path.join("test_data", "audio", "sample_voice_meal.wav")
    assert os.path.exists(audio_path), f"Аудиофайл не найден: {audio_path}"

    from faster_whisper import WhisperModel
    print("Запуск локальной модели Whisper (tiny, CPU, int8)...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, language="ru")
    recognized_text = " ".join([s.text for s in segments]).strip().lower()

    print(f"Язык: {info.language} (вероятность {info.language_probability:.2f})")
    print(f"Распознанный текст: «{recognized_text}»")

    # Проверяем ключевые смысловые маркеры
    assert any(w in recognized_text for w in ["завтрак", "яйц", "кофе"]), \
        "В распознанном тексте должны присутствовать ключевые слова завтрака!"
    print("✅ Локальный Whisper успешно и автономно расшифровал русскую речь!")


def test_queries_dataset_schema():
    print("\n--- ТЕСТ 2: Валидация дата-сета типовых сценариев ---")
    queries_path = os.path.join("test_data", "queries", "food_queries.json")
    assert os.path.exists(queries_path), f"Файл дата-сета не найден: {queries_path}"

    with open(queries_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dataset = data.get("dataset", {})
    required_sections = [
        "exact_scale_meals",
        "casual_snacks",
        "imprecise_home_cooking",
        "sweet_cravings_sos",
        "meal_replacement_requests",
        "fridge_inventory"
    ]

    total_samples = 0
    for sec in required_sections:
        assert sec in dataset, f"Секция {sec} отсутствует в дата-сете!"
        items = dataset[sec]
        assert len(items) > 0, f"Секция {sec} не должна быть пустой!"
        total_samples += len(items)
        print(f"• Секция [{sec}]: {len(items)} сценариев")

    print(f"✅ Дата-сет валиден: всего {total_samples} тестовых сценариев.")


async def test_offline_food_diary_pipeline():
    print("\n--- ТЕСТ 3: Оффлайн пайплайн Дневника питания и прогресс-баров ---")
    fixtures_path = os.path.join("test_data", "fixtures", "mock_llm_responses.json")
    with open(fixtures_path, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    parsed_meals = fixtures.get("parsed_meals", {})
    voice_meal = parsed_meals.get("voice_meal_sample")
    scale_meal = parsed_meals.get("scale_01")

    assert voice_meal and scale_meal, "Фикстуры блюд должны присутствовать!"

    test_user_id = 888777666
    test_date = datetime.now().strftime("%Y-%m-%d")

    # Очистка перед тестом
    await database.clear_daily_food_logs(test_user_id, test_date)

    # 1. Заносим распознанный завтрак из голосового
    id1 = await database.add_food_log(
        user_id=test_user_id,
        meal_type="Завтрак",
        food_description=voice_meal["dish_name"],
        calories=voice_meal["calories"],
        protein=voice_meal["protein"],
        fat=voice_meal["fat"],
        carbs=voice_meal["carbs"],
        log_date=test_date
    )
    assert id1 > 0

    # 2. Заносим обед с точными граммовками
    id2 = await database.add_food_log(
        user_id=test_user_id,
        meal_type="Обед",
        food_description=scale_meal["dish_name"],
        calories=scale_meal["calories"],
        protein=scale_meal["protein"],
        fat=scale_meal["fat"],
        carbs=scale_meal["carbs"],
        log_date=test_date
    )
    assert id2 > 0

    # 3. Проверяем расчет сумм в БД
    summary = await database.get_daily_summary(test_user_id, test_date)
    assert summary["meals_count"] == 2
    expected_cals = voice_meal["calories"] + scale_meal["calories"]  # 370 + 450 = 820
    assert summary["calories"] == expected_cals
    print(f"Сумма калорий за день в БД: {summary['calories']} ккал (ожидалось: {expected_cals})")

    # 4. Проверяем карточку с прогресс-баром
    dummy_profile = {
        "target_calories": 1650,
        "target_protein": 90,
        "target_fat": 58,
        "target_carbs": 195
    }
    logs = await database.get_daily_food_logs(test_user_id, test_date)
    card = nutrition.format_daily_diary_card(dummy_profile, logs, summary, test_date)
    assert "820 / 1650" in card
    assert "Завтрак" in card and "Обед" in card
    print("Визуальная карточка:\n" + card[:350] + "\n...")

    # Очистка
    await database.clear_daily_food_logs(test_user_id, test_date)
    print("✅ Пайплайн Дневника питания полностью проверен без единого сетевого запроса!")


async def test_offline_weight_dynamics():
    print("\n--- ТЕСТ 4: Проверка трекера динамики веса ---")
    test_user_id = 888777666

    await database.add_weight_entry(test_user_id, 65.0, "Старт")
    await database.add_weight_entry(test_user_id, 63.5, "Минус 1.5 кг")

    dyn = await database.get_weight_dynamics(test_user_id)
    assert dyn["has_data"] is True
    assert dyn["count"] >= 2
    assert round(dyn["total_diff"], 1) == -1.5
    print(f"Динамика: {dyn['start_weight']} кг ➡️ {dyn['current_weight']} кг (отвес: {dyn['total_diff']:.1f} кг)")

    # Очистка
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("DELETE FROM weight_history WHERE user_id = ?", (test_user_id,))
        await db.commit()
    print("✅ Трекер динамики веса работает штатно!")


def test_offline_vision_fixtures():
    print("\n--- ТЕСТ 5: Валидация эталонных фикстур Vision ---")
    fixtures_path = os.path.join("test_data", "fixtures", "mock_llm_responses.json")
    with open(fixtures_path, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    vision = fixtures.get("vision_results", {})
    plate = vision.get("plate_sample")
    logo = vision.get("logo_sample")

    assert plate["is_food"] is True
    assert plate["weight_g"] == 350.0
    assert len(plate["components"]) == 3

    assert logo["is_food"] is False
    assert logo["calories"] == 0.0
    print("✅ Фикстуры Vision валидны (поддерживают пищевые и непищевые сценарии).")


async def main():
    print("==========================================================")
    print("🥑 ЗАПУСК АВТОНОМНОГО ОФФЛАЙН-ТЕСТИРОВАНИЯ БОТА «ПИЩЕБЛОК»")
    print("==========================================================")
    await database.init_db()

    await test_whisper_offline()
    test_queries_dataset_schema()
    await test_offline_food_diary_pipeline()
    await test_offline_weight_dynamics()
    test_offline_vision_fixtures()

    print("\n==========================================================")
    print("🎉 ВСЕ 5 ОФФЛАЙН-ТЕСТОВ УСПЕШНО ПРОЙДЕНЫ (0 РУБ / 0 ТОКЕНОВ)!")
    print("==========================================================")


if __name__ == "__main__":
    asyncio.run(main())
