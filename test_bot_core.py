"""
Тест проверки работы ключевых модулей бота:
- База данных (миграции, расширенный профиль, Дневник питания, избранное)
- Нутрициологические расчеты (BMR, смена цели, прогресс-бары)
- Формирование системного промпта с учетом любимых продуктов и привычки готовки
- Дневник питания (добавление, сводка за день, удаление)
"""

import asyncio
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import database
import nutrition
import llm_service


async def run_tests():
    print("=== ТЕСТ 1: Инициализация БД и миграции ===")
    await database.init_db()
    print("✅ Таблицы users, favorites, chat_messages и daily_food_logs инициализированы.")

    print("\n=== ТЕСТ 2: Сохранение и чтение расширенного профиля ===")
    test_user_id = 99999999
    profile_data = {
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
        "is_onboarded": 1
    }
    await database.save_user_profile(test_user_id, profile_data)
    loaded = await database.get_user_profile(test_user_id)
    assert loaded is not None, "Профиль не найден"
    assert loaded["gender"] == "женский"
    assert loaded["age"] == 28
    assert loaded["favorite_foods"] == "манго, пармезан, горький шоколад, авокадо"
    assert "2-3" in loaded["cooking_habit"]
    assert "08:30" in loaded["meal_schedule"]
    print("✅ Расширенный профиль успешно сохранен и прочитан со всеми новыми параметрами.")

    print("\n=== ТЕСТ 3: Точечное изменение цели и веса без потери данных ===")
    # 1. Изменение цели на "поддержание формы"
    new_targets = nutrition.calculate_bmr_and_targets(
        gender=loaded["gender"],
        age=loaded["age"],
        height=loaded["height"],
        weight=loaded["weight"],
        activity=loaded["activity"],
        goal="поддержание формы и тонус"
    )
    await database.update_profile_fields(test_user_id, {
        "goal": "поддержание формы и тонус",
        **new_targets
    })
    updated = await database.get_user_profile(test_user_id)
    assert updated["goal"] == "поддержание формы и тонус"
    assert updated["favorite_foods"] == loaded["favorite_foods"], "Любимые продукты стерлись!"
    assert updated["allergies"] == loaded["allergies"], "Аллергии стерлись!"
    assert updated["target_calories"] > profile_data["target_calories"], "Калории при поддержании должны быть выше, чем при снижении"

    # 2. Обновление веса на 57.0 кг
    new_weight = 57.0
    weight_targets = nutrition.calculate_bmr_and_targets(
        gender=updated["gender"],
        age=updated["age"],
        height=updated["height"],
        weight=new_weight,
        activity=updated["activity"],
        goal=updated["goal"]
    )
    await database.update_profile_fields(test_user_id, {
        "weight": new_weight,
        **weight_targets
    })
    weight_updated = await database.get_user_profile(test_user_id)
    assert weight_updated["weight"] == 57.0
    print("✅ Быстрое изменение цели и веса пересчитывает КБЖУ, сохраняя все остальные поля в целости.")

    print("\n=== ТЕСТ 4: Проверка системного промпта LLM ===")
    system_prompt = llm_service.build_nutritionist_system_prompt(loaded)
    assert "манго, пармезан, горький шоколад" in system_prompt, "Любимые продукты не попали в промпт"
    assert "ГОТОВИТЬ НА 2-3 ДНЯ ВПЕРЁД" in system_prompt, "Привычка готовки не учтена в промпте"
    assert "08:30" in system_prompt, "Режим питания не попал в промпт"
    assert "арахис, лактоза" in system_prompt, "Аллергии не попали в промпт"
    assert "кинза, вареный лук" in system_prompt, "Стоп-лист не попал в промпт"
    print("✅ Системный промпт нутрициолога содержит любимые продукты, режим и формат готовки.")

    print("\n=== ТЕСТ 5: Дневник питания (добавление, расчет суммы за день, удаление) ===")
    test_date = "2026-09-20"
    await database.clear_daily_food_logs(test_user_id, test_date)

    # Добавляем завтрак
    log1 = await database.add_food_log(
        user_id=test_user_id,
        meal_type="Завтрак",
        food_description="Овсянка 50г, ягоды 70г, 2 яйца",
        calories=420.0,
        protein=24.0,
        fat=14.0,
        carbs=48.0,
        log_date=test_date
    )
    assert log1 > 0

    # Добавляем обед
    log2 = await database.add_food_log(
        user_id=test_user_id,
        meal_type="Обед",
        food_description="Гречка 80г, куриное филе 130г, овощной салат 150г",
        calories=510.0,
        protein=42.0,
        fat=11.0,
        carbs=58.0,
        log_date=test_date
    )
    assert log2 > 0

    # Проверяем получение записей
    logs = await database.get_daily_food_logs(test_user_id, test_date)
    assert len(logs) == 2
    assert logs[0]["meal_type"] == "Завтрак"
    assert logs[1]["meal_type"] == "Обед"

    # Проверяем суммарный расчет
    summary = await database.get_daily_summary(test_user_id, test_date)
    assert summary["meals_count"] == 2
    assert summary["calories"] == 930.0  # 420 + 510
    assert summary["protein"] == 66.0   # 24 + 42
    assert summary["fat"] == 25.0       # 14 + 11
    assert summary["carbs"] == 106.0    # 48 + 58
    print("✅ Добавление приемов пищи и суммирование КБЖУ работают точно.")

    # Проверяем форматирование карточки дневника с прогресс-баром
    card_text = nutrition.format_daily_diary_card(loaded, logs, summary, test_date)
    assert "930 /" in card_text
    assert "Осталось до вашей нормы" in card_text
    assert "Овсянка" in card_text
    print("✅ Карточка Дневника питания сформирована наглядно со всеми прогресс-барами.")

    # Удаление отдельной записи
    deleted = await database.delete_food_log(log1, test_user_id)
    assert deleted is True
    logs_after = await database.get_daily_food_logs(test_user_id, test_date)
    assert len(logs_after) == 1
    summary_after = await database.get_daily_summary(test_user_id, test_date)
    assert summary_after["calories"] == 510.0

    # Очистка дня
    await database.clear_daily_food_logs(test_user_id, test_date)
    logs_empty = await database.get_daily_food_logs(test_user_id, test_date)
    assert len(logs_empty) == 0
    print("✅ Удаление отдельного приема пищи и полная очистка дня работают корректно.")

    print("\n=== ТЕСТ 6: Проверка Избранного ===")
    fav_id = await database.add_favorite(
        user_id=test_user_id,
        category="kbzhu",
        title="📊 Расчет КБЖУ (обед в 15:10)",
        content="• Говядина запеченная (138 г): ~331 ккал\nИТОГО: 466 ккал"
    )
    assert fav_id > 0
    favs = await database.get_favorites(test_user_id)
    assert len(favs) >= 1
    deleted = await database.delete_favorite(fav_id, test_user_id)
    assert deleted is True

    # Проверка сохранения списка покупок в Избранное
    from handlers.menu_planner import CURRENT_SHOPPING_LISTS, format_shopping_share_text
    CURRENT_SHOPPING_LISTS[test_user_id] = [
        {"name": "Томаты (500 г)", "checked": False},
        {"name": "Творог 5% (400 г)", "checked": True}
    ]
    shop_content = format_shopping_share_text(CURRENT_SHOPPING_LISTS[test_user_id])
    assert "Томаты" in shop_content and "Творог" in shop_content

    shop_fav_id = await database.add_favorite(
        user_id=test_user_id,
        category="shopping",
        title="🛒 Список покупок",
        content=shop_content
    )
    assert shop_fav_id > 0
    shop_favs = await database.get_favorites(test_user_id)
    import keyboards
    favs_list_kb = keyboards.get_favorites_list_keyboard(shop_favs)
    btn_texts = [btn.text for row in favs_list_kb.inline_keyboard for btn in row]
    assert any("🛒" in t and "Список покупок" in t for t in btn_texts)

    # Проверка клавиатуры просмотра записи списка покупок с кнопкой пересылки и копирования
    fav_item_kb = keyboards.get_favorite_item_keyboard(
        shop_fav_id,
        share_url="https://t.me/share/url?url=https://t.me&text=test",
        share_text="test"
    )
    item_urls = [btn.url for row in fav_item_kb.inline_keyboard for btn in row if btn.url]
    assert len(item_urls) == 1 and item_urls[0].startswith("https://t.me/share/url?url=https://t.me&text=")
    fav_copy_btns = [btn for row in fav_item_kb.inline_keyboard for btn in row if getattr(btn, "copy_text", None)]
    assert len(fav_copy_btns) == 1 and fav_copy_btns[0].copy_text.text == "test"

    deleted_shop = await database.delete_favorite(shop_fav_id, test_user_id)
    assert deleted_shop is True
    print("✅ Сохранение и просмотр Списка покупок в Избранном работают точно (с товарами, пересылкой и копированием).")
    print("\n=== ТЕСТ 7: Проверка клавиатур (SOS и Vision) ===")
    from keyboards import get_main_keyboard, get_vision_log_keyboard
    main_kb = get_main_keyboard()
    all_buttons = [btn.text for row in main_kb.keyboard for btn in row]
    assert "🍫 SOS: Сладкое / Срыв" in all_buttons
    assert "📸 Фото тарелки (Vision)" in all_buttons and "🎙️ Голосовой ввод (Whisper)" in all_buttons
    v_kb = get_vision_log_keyboard()
    v_cbs = [btn.callback_data for row in v_kb.inline_keyboard for btn in row]
    assert "vlog_Завтрак" in v_cbs and "vlog_Обед" in v_cbs and "vlog_cancel" in v_cbs
    print("✅ Главная клавиатура с кнопками SOS, Фото (Vision) и Голоса (Whisper) проверены.")

    print("\n=== ТЕСТ 8: Трекер динамики веса (weight_history) ===")
    await database.add_weight_entry(test_user_id, 62.0, "Старт")
    await database.add_weight_entry(test_user_id, 60.5, "Неделя 1")
    dyn = await database.get_weight_dynamics(test_user_id)
    assert dyn["has_data"] is True
    assert dyn["count"] >= 2
    assert round(dyn["total_diff"], 1) == -1.5
    # Очистка
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("DELETE FROM weight_history WHERE user_id = ?", (test_user_id,))
        await db.commit()
    print("✅ Трекер динамики веса и расчет отвеса работают точно.")

    print("\n=== ТЕСТ 9: Гендерная адаптация и пересчет BMR ===")
    from handlers.menu_planner import extract_shopping_list_items, format_shopping_share_text
    import keyboards

    male_targets = nutrition.calculate_bmr_and_targets("мужской", 30, 175, 75, "умеренная", "поддержание")
    female_targets = nutrition.calculate_bmr_and_targets("женский", 30, 175, 75, "умеренная", "поддержание")
    assert male_targets["bmr"] - female_targets["bmr"] == 166.0, "Разница BMR между мужчиной (+5) и женщиной (-161) должна быть ровно 166 ккал"

    male_profile = {
        "gender": "мужской",
        "age": 30,
        "height": 175,
        "weight": 75,
        "persons_count": 1,
        "activity": "умеренная",
        "goal": "поддержание формы",
        "target_calories": 2400,
        "target_protein": 120,
        "target_fat": 75,
        "target_carbs": 300
    }
    male_card = nutrition.format_profile_card(male_profile)
    assert "на меня одного 👨" in male_card
    assert "на меня одну 👩" not in male_card

    male_prompt = llm_service.build_nutritionist_system_prompt(male_profile)
    assert "ПОДОПЕЧНОГО" in male_prompt
    assert "ПОДОПЕЧНОЙ" not in male_prompt
    assert "тестостерон" in male_prompt
    print("✅ Гендерная персонализация (BMR, карточка, промпты LLM) проверена на 100%.")

    print("\n=== ТЕСТ 10: Интерактивный список покупок, замена блюд и семейный ужин ===")
    # Проверка клавиатуры быстрой смены пола
    gender_kb = keyboards.get_gender_change_keyboard()
    g_cbs = [btn.callback_data for row in gender_kb.inline_keyboard for btn in row]
    assert "setgender_male" in g_cbs and "setgender_female" in g_cbs

    # Проверка кнопок замены блюд в меню на день
    day_actions_kb = keyboards.get_day_menu_actions_keyboard()
    day_cbs = [btn.callback_data for row in day_actions_kb.inline_keyboard for btn in row]
    assert "repmeal_Завтрак" in day_cbs and "repmeal_Обед" in day_cbs and "repmeal_Ужин" in day_cbs

    # Интерактивный список покупок
    items = [
        {"name": "Огурцы (500 г)", "checked": False},
        {"name": "Куриное филе (1 кг)", "checked": True}
    ]
    share_text = format_shopping_share_text(items)
    assert "▫️ Огурцы" in share_text
    assert "✅ Куриное филе" in share_text

    shop_kb = keyboards.get_interactive_shopping_keyboard(items, share_text=share_text)
    btn_urls = [btn.url for row in shop_kb.inline_keyboard for btn in row if btn.url]
    assert len(btn_urls) == 1 and btn_urls[0].startswith("https://t.me/share/url?url=https://t.me&text=")
    shop_copy_btns = [btn for row in shop_kb.inline_keyboard for btn in row if getattr(btn, "copy_text", None)]
    assert len(shop_copy_btns) == 1 and shop_copy_btns[0].copy_text.text == share_text
    shop_clean_cbs = [btn.callback_data for row in shop_kb.inline_keyboard for btn in row if btn.callback_data == "shop_send_clean"]
    assert len(shop_clean_cbs) == 1

    # Парсинг списка покупок
    menu_sample = "### 🛒 Список покупок на неделю:\n- Томаты (500 г)\n- Творог 5% (400 г)\n\nПриятного аппетита!"
    parsed_items = extract_shopping_list_items(menu_sample)
    assert len(parsed_items) == 2
    assert "Томаты (500 г)" in parsed_items

    # Проверка кнопок выбора альтернативных вариантов блюд
    var_choice_kb = keyboards.get_meal_variant_choice_keyboard("Завтрак")
    var_cbs = [btn.callback_data for row in var_choice_kb.inline_keyboard for btn in row]
    assert "selvar_Завтрак_1" in var_cbs and "selvar_Завтрак_2" in var_cbs and "save_fav_recipe" in var_cbs

    # Проверка парсинга вариантов блюд (Вариант 1 и Вариант 2)
    sample_rep = """
    ## 🥣 Вариант 1. «Овсянка по-спортивному» с творогом
    - Вес порции: ~430 г
    - КБЖУ порции: ~720 ккал | Б 34 г | Ж 22 г | У 88 г
    ---
    ## 🍳 Вариант 2. «Белковый омлет с сыром»
    - Вес порции: ~500 г
    - КБЖУ порции: ~710 ккал | Б 36 г | Ж 27 г | У 77 г
    """
    from handlers.menu_planner import extract_replacement_variants
    variants = extract_replacement_variants(sample_rep, "Завтрак")
    assert variants["1"]["calories"] == 720.0
    assert variants["1"]["protein"] == 34.0
    assert variants["2"]["calories"] == 710.0
    assert variants["2"]["protein"] == 36.0
    assert "Овсянка" in variants["1"]["dish_name"]
    assert "омлет" in variants["2"]["dish_name"].lower()

    print("✅ Интерактивный список покупок, кнопка пересылки t.me/share/url, замена блюд и выбор вариантов работают штатно.")

    # Финальная очистка тестового пользователя
    async with database.aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (test_user_id,))
        await db.commit()

    print("\n🎉 ВСЕ 10 ТЕСТОВЫХ СЬЮТОВ ПРОЙДЕНЫ НА 100% УСПЕШНО!")


if __name__ == "__main__":
    asyncio.run(run_tests())

