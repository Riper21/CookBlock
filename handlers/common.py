"""
Обработчик базовых команд: /start, /help, /reset, отмена и свободный диалог.
"""

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database import get_user_profile, init_db
from nutrition import format_profile_card, get_random_wish
from keyboards import (
    get_main_keyboard,
    get_gender_keyboard,
    get_profile_actions_keyboard,
    get_save_favorite_keyboard
)
from states import ProfileForm
import llm_service

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start — приветствие и запуск анкеты, если профиль не заполнен."""
    await state.clear()
    profile = await get_user_profile(message.from_user.id)

    if not profile or not profile.get("is_onboarded"):
        await message.answer(
            f"👋 **Приветствую, {message.from_user.first_name or 'друг'}!**\n\n"
            "Я — твой персональный **диетолог-нутрициолог и заботливый шеф-повар** 🥑✨\n\n"
            "Моя цель — помочь тебе питаться сбалансированно, вкусно и легко, "
            "составлять меню из доступных продуктов, подбирать идеальные перекусы "
            "и считать КБЖУ без стресса и строгих диет.\n\n"
            "Давай познакомимся и настроим твой профиль питания! Это займёт 1 минуту.\n\n"
            "👉 **Укажи свой пол:**",
            reply_markup=get_gender_keyboard(),
            parse_mode="Markdown"
        )
        await state.set_state(ProfileForm.gender)
    else:
        await message.answer(
            f"👋 С возвращением, **{message.from_user.first_name or 'друг'}**!\n\n"
            "Я готов помочь спланировать рацион, рассчитать блюдо или придумать рецепт.\n\n"
            f"_{get_random_wish()}_\n\n"
            "Выбери нужный раздел на клавиатуре ниже:",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )


@router.message(F.text == "❌ Отмена / Главное меню")
@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Отмена текущего сценария и возврат в главное меню."""
    await state.clear()
    await message.answer(
        "Действие отменено. Вы вернулись в главное меню 👇",
        reply_markup=get_main_keyboard()
    )


@router.message(F.text == "🔄 Сброс диалога")
@router.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    """Сброс контекста беседы."""
    await state.clear()
    await llm_service.reset_chat_history(message.from_user.id)
    await message.answer(
        "🔄 История диалога очищена! Ваши параметры профиля и избранное сохранены.\n"
        "Чем могу помочь прямо сейчас?",
        reply_markup=get_main_keyboard()
    )


@router.message(F.text == "👤 Мой профиль и КБЖУ")
@router.message(Command("profile"))
async def cmd_profile(message: types.Message):
    """Просмотр текущего профиля и нормы КБЖУ."""
    profile = await get_user_profile(message.from_user.id)
    if not profile or not profile.get("is_onboarded"):
        await message.answer(
            "Ваш профиль ещё не настроен. Давайте заполним анкету!",
            reply_markup=get_gender_keyboard()
        )
        return

    text = format_profile_card(profile)
    await message.answer(
        text,
        reply_markup=get_profile_actions_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text)
async def handle_free_text(message: types.Message, state: FSMContext):
    """
    Обработка свободных текстовых сообщений:
    - Вопросы по питанию
    - Оценка дневного рациона
    - Подбор полезных сочетаний
    """
    # Если пользователь сейчас находится в каком-то состоянии FSM, не перехватываем
    current_state = await state.get_state()
    if current_state is not None:
        return

    profile = await get_user_profile(message.from_user.id)
    if not profile:
        profile = {}

    # Отправляем индикатор набора текста
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        reply = await llm_service.general_nutrition_chat(message.from_user.id, profile, message.text)
        chunks = [reply[i:i + 4000] for i in range(0, len(reply), 4000)]
        for i, chunk in enumerate(chunks):
            kb = get_save_favorite_keyboard("general") if i == len(chunks) - 1 else None
            try:
                await message.answer(chunk, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await message.answer(chunk, reply_markup=kb, parse_mode=None)
    except Exception as e:
        await message.answer(
            f"⚠️ Ошибка при обращении к сервису питания: {e}\n"
            "Пожалуйста, повторите попытку или проверьте настройки ключа API.",
            parse_mode=None
        )
