"""
Обработчик расчета КБЖУ по описанию блюда или приема пищи.
Позволяет рассчитать КБЖУ любого блюда и в 1 клик записать его в Дневник питания
(в Завтрак, Обед, Ужин или Перекус) либо сохранить в Избранное.
"""

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database import get_user_profile, add_food_log
from states import KbzhuForm
from keyboards import (
    get_main_keyboard,
    get_cancel_keyboard,
    get_meal_type_log_keyboard
)
import llm_service

router = Router()

# Временное хранилище последнего рассчитанного блюда для быстрой записи по кнопке:
# { user_id: { "dish_name": str, "calories": float, "protein": float, "fat": float, "carbs": float } }
LAST_CALCULATED_MEALS: dict = {}


@router.message(F.text == "📊 Рассчитать КБЖУ блюда")
@router.message(Command("kbzhu"))
async def start_kbzhu_calc(message: types.Message, state: FSMContext):
    """Запрос описания блюда для расчета КБЖУ."""
    await message.answer(
        "📊 **Расчет КБЖУ блюда или перекуса**\n\n"
        "Отправьте состав вашего приема пищи (с граммовками или примерным описанием).\n\n"
        "**Примеры:**\n"
        "• _«Обед: говядина запеченная 138г, рис отварной 80г, болгарский перец 51г, огурец 20г, оливковое масло 1г»_\n"
        "• _«Завтрак: 2 хлебца (10г), авокадо 40г, слабосоленая форель 50г, фильтр-кофе»_\n"
        "• _«Перекус: мандарины 150г и 20г темного шоколада»_\n\n"
        "Я распишу КБЖУ каждого ингредиента, пользу для организма и предложу сразу занести в Дневник питания!",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(KbzhuForm.waiting_for_meal_description)


@router.message(KbzhuForm.waiting_for_meal_description)
async def process_kbzhu_calc(message: types.Message, state: FSMContext):
    """Расчет КБЖУ через LLM и предложение записать в дневник."""
    meal_text = message.text.strip()
    await state.clear()

    profile = await get_user_profile(message.from_user.id)
    if not profile:
        profile = {}

    status_msg = await message.answer(
        "⚖️ Считаю калории, белки, жиры, углеводы и микронутриенты...",
        reply_markup=get_main_keyboard()
    )
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Детальный отчет для пользователя
        calc_result = await llm_service.calculate_dish_kbzhu(profile, meal_text)
        # Точное извлечение КБЖУ напрямую из сформированного отчета (Zero Divergence)
        parsed_data = llm_service.extract_kbzhu_from_calc_result(calc_result, fallback_dish_name=meal_text[:30])
        if parsed_data.get("calories", 0.0) <= 0:
            parsed_data = await llm_service.parse_meal_kbzhu(meal_text, profile)
        LAST_CALCULATED_MEALS[message.from_user.id] = parsed_data

        await status_msg.delete()

        chunks = [calc_result[i:i + 4000] for i in range(0, len(calc_result), 4000)]
        for i, chunk in enumerate(chunks):
            kb = get_meal_type_log_keyboard() if i == len(chunks) - 1 else None
            try:
                await message.answer(chunk, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await message.answer(chunk, reply_markup=kb, parse_mode=None)

    except Exception as e:
        await message.answer(
            f"⚠️ Ошибка при расчете КБЖУ: {e}\n"
            "Пожалуйста, попробуйте еще раз.",
            reply_markup=get_main_keyboard(),
            parse_mode=None
        )


@router.callback_query(F.data.startswith("logmeal_"))
async def process_log_meal_callback(callback: types.CallbackQuery):
    """Запись ранее рассчитанного блюда в выбранный прием пищи дневника."""
    meal_type = callback.data.replace("logmeal_", "")
    user_id = callback.from_user.id
    meal_data = LAST_CALCULATED_MEALS.get(user_id)

    if not meal_data:
        await callback.answer("Данные блюда устарели. Рассчитайте блюдо заново.", show_alert=True)
        return

    log_id = await add_food_log(
        user_id=user_id,
        meal_type=meal_type,
        food_description=meal_data["dish_name"],
        calories=meal_data["calories"],
        protein=meal_data["protein"],
        fat=meal_data["fat"],
        carbs=meal_data["carbs"]
    )

    await callback.answer(f"Записано в {meal_type}!")
    await callback.message.answer(
        f"✅ **{meal_type} успешно добавлен в Дневник питания!**\n\n"
        f"🍽️ _{meal_data['dish_name']}_\n"
        f"🔥 +{meal_data['calories']:.0f} ккал | "
        f"Б: {meal_data['protein']:.1f}г | "
        f"Ж: {meal_data['fat']:.1f}г | "
        f"У: {meal_data['carbs']:.1f}г\n\n"
        "Чтобы посмотреть общую сумму за день, нажмите кнопку **📖 Дневник питания 🥑** ниже 👇",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
