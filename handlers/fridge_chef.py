"""
Обработчик подбора рецептов из имеющихся продуктов в холодильнике/шкафу.
Позволяет получить рецепт и в 1 клик записать его точное КБЖУ в Дневник питания.
"""

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database import get_user_profile
from states import FridgeForm
from keyboards import (
    get_main_keyboard,
    get_cancel_keyboard,
    get_fridge_recipe_keyboard
)
from handlers.kbzhu_calc import LAST_CALCULATED_MEALS
import llm_service

router = Router()


@router.message(F.text == "🍳 Рецепт из холодильника")
@router.message(Command("fridge"))
async def start_fridge_recipe(message: types.Message, state: FSMContext):
    """Запрос списка продуктов из холодильника."""
    await message.answer(
        "🍳 **Шеф-повар у холодильника**\n\n"
        "Напишите, какие продукты у вас есть в наличии "
        "_(например: 2 яйца, кабачок, банка тунца, остатки сыра, помидор)_.\n\n"
        "Я придумаю простое, полезное блюдо с расчетом КБЖУ и точным весом порции в граммах!",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(FridgeForm.waiting_for_ingredients)


@router.message(FridgeForm.waiting_for_ingredients)
async def process_fridge_recipe(message: types.Message, state: FSMContext):
    """Генерация рецепта на основе продуктов и сохранение данных для быстрой записи в дневник."""
    products = message.text.strip()
    await state.clear()

    profile = await get_user_profile(message.from_user.id)
    if not profile:
        profile = {}

    status_msg = await message.answer(
        "👩‍🍳 Колдую над рецептом с учетом ваших предпочтений... 🍲",
        reply_markup=get_main_keyboard()
    )
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        recipe_text = await llm_service.generate_fridge_recipe(profile, products)
        await status_msg.delete()

        # Точное извлечение КБЖУ напрямую из рецепта шефа (Zero Divergence)
        parsed_data = llm_service.extract_kbzhu_from_calc_result(recipe_text, fallback_dish_name="Блюдо из холодильника")
        LAST_CALCULATED_MEALS[message.from_user.id] = parsed_data

        chunks = [recipe_text[i:i + 4000] for i in range(0, len(recipe_text), 4000)]
        for i, chunk in enumerate(chunks):
            kb = get_fridge_recipe_keyboard() if i == len(chunks) - 1 else None
            try:
                await message.answer(chunk, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await message.answer(chunk, reply_markup=kb, parse_mode=None)

    except Exception as e:
        await message.answer(
            f"⚠️ Ошибка при подборе рецепта: {e}\n"
            "Пожалуйста, повторите попытку.",
            reply_markup=get_main_keyboard(),
            parse_mode=None
        )
