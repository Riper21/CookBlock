"""
Обработчик Дневника питания (Food Diary).
Позволяет пользователю в реальном времени отслеживать съеденную за день еду,
считать суммарные калории и БЖУ, видеть наглядный прогресс-бар нормы
и получать персональные рекомендации нутрициолога на остаток дня.
"""

from datetime import datetime
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database import (
    get_user_profile,
    get_daily_food_logs,
    get_daily_summary,
    add_food_log,
    delete_food_log,
    clear_daily_food_logs
)
from states import FoodDiaryForm
from keyboards import (
    get_main_keyboard,
    get_cancel_keyboard,
    get_food_diary_keyboard,
    get_delete_food_log_keyboard
)
from nutrition import format_daily_diary_card
import llm_service

router = Router()


@router.message(F.text == "📖 Дневник питания 🥑")
@router.message(Command("diary"))
async def show_daily_diary(message: types.Message):
    """Отображение текущего состояния Дневника питания за сегодня."""
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)

    if not profile or not profile.get("is_onboarded"):
        await message.answer(
            "⚠️ Сначала заполните параметры в разделе **👤 Мой профиль и КБЖУ**, "
            "чтобы бот знал вашу индивидуальную норму калорий и БЖУ!",
            reply_markup=get_main_keyboard()
        )
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    logs = await get_daily_food_logs(user_id, today_str)
    summary = await get_daily_summary(user_id, today_str)

    diary_text = format_daily_diary_card(profile, logs, summary, today_str)
    has_logs = len(logs) > 0

    await message.answer(
        diary_text,
        reply_markup=get_food_diary_keyboard(has_logs=has_logs),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "diary_refresh")
async def refresh_diary_callback(callback: types.CallbackQuery):
    """Обновление карточки дневника в сообщении."""
    await callback.answer("Данные обновлены")
    user_id = callback.from_user.id
    profile = await get_user_profile(user_id)
    if not profile:
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    logs = await get_daily_food_logs(user_id, today_str)
    summary = await get_daily_summary(user_id, today_str)

    diary_text = format_daily_diary_card(profile, logs, summary, today_str)
    has_logs = len(logs) > 0

    try:
        await callback.message.edit_text(
            diary_text,
            reply_markup=get_food_diary_keyboard(has_logs=has_logs),
            parse_mode="Markdown"
        )
    except Exception:
        pass


@router.callback_query(F.data == "diary_add_meal")
async def start_add_meal_to_diary(callback: types.CallbackQuery, state: FSMContext):
    """Начало сценария быстрого добавления еды в дневник."""
    await callback.answer()
    await state.set_state(FoodDiaryForm.waiting_for_dish_text)
    await callback.message.answer(
        "✍️ **Что вы съели?**\n\n"
        "Опишите прием пищи своими словами (можно с граммовками или порциями):\n\n"
        "**Примеры:**\n"
        "• _«Завтрак: овсянка 50г, горсть ягод и кофе с молоком»_\n"
        "• _«Обед: суп куриный с лапшой тарелка, 2 куска хлеба»_\n"
        "• _«Перекус: яблоко 150г и 20г миндаля»_\n"
        "• _«Ужин: запеченная рыба 150г и овощной салат»_\n\n"
        "Бот сам рассчитает калории, белки, жиры и углеводы и сразу добавит в сумму дня!",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )


@router.message(FoodDiaryForm.waiting_for_dish_text)
async def process_food_entry_text(message: types.Message, state: FSMContext):
    """Обработка текста съеденного, расчет КБЖУ через LLM и занесение в БД."""
    text = message.text.strip()
    await state.clear()

    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    if not profile:
        profile = {}

    status_msg = await message.answer(
        "⚖️ Считаю КБЖУ и заношу в дневник... ⏳",
        reply_markup=get_main_keyboard()
    )
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Парсинг КБЖУ через LLM
        parsed = await llm_service.parse_meal_kbzhu(text, profile)

        # Автоопределение типа приема пищи по ключевым словам
        text_lower = text.lower()
        if "завтрак" in text_lower:
            meal_type = "Завтрак"
        elif "обед" in text_lower:
            meal_type = "Обед"
        elif "ужин" in text_lower:
            meal_type = "Ужин"
        elif "перекус" in text_lower or "полдник" in text_lower:
            meal_type = "Перекус"
        else:
            # Определение по текущему времени
            current_hour = datetime.now().hour
            if 5 <= current_hour < 12:
                meal_type = "Завтрак"
            elif 12 <= current_hour < 17:
                meal_type = "Обед"
            elif 17 <= current_hour < 22:
                meal_type = "Ужин"
            else:
                meal_type = "Перекус"

        # Запись в БД
        today_str = datetime.now().strftime("%Y-%m-%d")
        await add_food_log(
            user_id=user_id,
            meal_type=meal_type,
            food_description=parsed["dish_name"],
            calories=parsed["calories"],
            protein=parsed["protein"],
            fat=parsed["fat"],
            carbs=parsed["carbs"],
            log_date=today_str
        )

        await status_msg.delete()

        # Показываем подтверждение и обновленный дневник
        logs = await get_daily_food_logs(user_id, today_str)
        summary = await get_daily_summary(user_id, today_str)
        diary_text = format_daily_diary_card(profile, logs, summary, today_str)

        await message.answer(
            f"✅ **Записано в {meal_type}!**\n"
            f"🍽️ _{parsed['dish_name']}_: +{parsed['calories']:.0f} ккал (Б: {parsed['protein']:.1f}г, Ж: {parsed['fat']:.1f}г, У: {parsed['carbs']:.1f}г)\n\n"
            + diary_text,
            reply_markup=get_food_diary_keyboard(has_logs=True),
            parse_mode="Markdown"
        )

    except Exception as e:
        await message.answer(
            f"⚠️ Не удалось рассчитать блюдо: {e}\n"
            "Пожалуйста, попробуйте еще раз.",
            reply_markup=get_main_keyboard()
        )


@router.callback_query(F.data == "diary_advice")
async def advice_for_remaining_day(callback: types.CallbackQuery):
    """Совет нутрициолога на остаток дня исходя из оставшегося КБЖУ."""
    await callback.answer("Готовлю рекомендацию...")
    user_id = callback.from_user.id
    profile = await get_user_profile(user_id)
    if not profile:
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    logs = await get_daily_food_logs(user_id, today_str)
    summary = await get_daily_summary(user_id, today_str)

    target_cals = float(profile.get("target_calories", 1800.0))
    target_prot = float(profile.get("target_protein", 90.0))
    target_fat = float(profile.get("target_fat", 60.0))
    target_carbs = float(profile.get("target_carbs", 220.0))

    eaten_cals = float(summary.get("calories", 0.0))
    eaten_prot = float(summary.get("protein", 0.0))
    eaten_fat = float(summary.get("fat", 0.0))
    eaten_carbs = float(summary.get("carbs", 0.0))

    remaining = {
        "calories": max(0.0, target_cals - eaten_cals),
        "protein": max(0.0, target_prot - eaten_prot),
        "fat": max(0.0, target_fat - eaten_fat),
        "carbs": max(0.0, target_carbs - eaten_carbs)
    }

    await callback.message.bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")
    advice_text = await llm_service.generate_remaining_day_advice(profile, remaining, summary, logs)

    chunks = [advice_text[i:i + 4000] for i in range(0, len(advice_text), 4000)]
    for chunk in chunks:
        try:
            await callback.message.answer(chunk, parse_mode="Markdown")
        except Exception:
            await callback.message.answer(chunk, parse_mode=None)


@router.callback_query(F.data == "diary_delete_menu")
async def show_delete_menu(callback: types.CallbackQuery):
    """Показ списка приемов пищи за сегодня для выбора удаляемого."""
    await callback.answer()
    user_id = callback.from_user.id
    today_str = datetime.now().strftime("%Y-%m-%d")
    logs = await get_daily_food_logs(user_id, today_str)

    if not logs:
        await callback.answer("Записей за сегодня нет.", show_alert=True)
        return

    await callback.message.edit_text(
        "🗑️ **Выберите прием пищи, который нужно удалить из дневника:**",
        reply_markup=get_delete_food_log_keyboard(logs),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("dellog_"))
async def process_delete_log_item(callback: types.CallbackQuery):
    """Удаление выбранной записи."""
    log_id = int(callback.data.replace("dellog_", ""))
    user_id = callback.from_user.id
    await delete_food_log(log_id, user_id)
    await callback.answer("Запись удалена!")

    profile = await get_user_profile(user_id)
    today_str = datetime.now().strftime("%Y-%m-%d")
    logs = await get_daily_food_logs(user_id, today_str)
    summary = await get_daily_summary(user_id, today_str)
    diary_text = format_daily_diary_card(profile, logs, summary, today_str)

    await callback.message.edit_text(
        diary_text,
        reply_markup=get_food_diary_keyboard(has_logs=len(logs) > 0),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "diary_clear_day")
async def process_clear_today_diary(callback: types.CallbackQuery):
    """Очистка всех записей за сегодня."""
    user_id = callback.from_user.id
    today_str = datetime.now().strftime("%Y-%m-%d")
    await clear_daily_food_logs(user_id, today_str)
    await callback.answer("Дневник за сегодня очищен!")

    profile = await get_user_profile(user_id)
    logs = await get_daily_food_logs(user_id, today_str)
    summary = await get_daily_summary(user_id, today_str)
    diary_text = format_daily_diary_card(profile, logs, summary, today_str)

    await callback.message.edit_text(
        diary_text,
        reply_markup=get_food_diary_keyboard(has_logs=False),
        parse_mode="Markdown"
    )
