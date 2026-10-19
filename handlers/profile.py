"""
Обработчик анкеты и профиля пользователя (FSM).
Позволяет настроить все параметры: пол, возраст, рост, вес, формат питания,
активность, цели, любимые продукты (для радости), частоту готовки, режим дня,
аллергии и стоп-лист, а также точечно редактировать цель и вес без перезаполнения анкеты.
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from states import ProfileForm, QuickEditForm
from keyboards import (
    get_main_keyboard,
    get_gender_keyboard,
    get_gender_change_keyboard,
    get_persons_keyboard,
    get_activity_keyboard,
    get_goal_keyboard,
    get_change_goal_keyboard,
    get_cooking_habit_keyboard,
    get_skip_keyboard,
    get_cancel_keyboard,
    get_profile_actions_keyboard,
    get_stoplist_edit_keyboard,
    get_allergies_edit_keyboard
)
from database import save_user_profile, update_profile_fields, get_user_profile
from nutrition import calculate_bmr_and_targets, format_profile_card

router = Router()


# ==================== СТАРТ ПОЛНОЙ АНКЕТЫ ====================

@router.callback_query(F.data == "edit_full_profile")
async def start_reprofile(callback: types.CallbackQuery, state: FSMContext):
    """Перезапуск анкеты по кнопке в профиле."""
    await callback.answer()
    await state.clear()
    await callback.message.answer(
        "📝 **Давайте настроим ваши параметры питания!**\n\n"
        "👉 **Укажите ваш пол:**",
        reply_markup=get_gender_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.gender)


@router.callback_query(ProfileForm.gender, F.data.startswith("gender_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    """Выбор пола."""
    gender = "женский" if "female" in callback.data else "мужской"
    await state.update_data(gender=gender)
    await callback.answer(f"Выбран {gender} пол")

    await callback.message.edit_text(
        f"✅ Пол: **{gender.capitalize()}**\n\n"
        "👉 **Введите ваш возраст (полных лет):**\n"
        "_(например: 28)_",
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.age)


@router.message(ProfileForm.age)
async def process_age(message: types.Message, state: FSMContext):
    """Ввод возраста."""
    text = message.text.strip()
    if not text.isdigit() or not (12 <= int(text) <= 100):
        await message.answer("⚠️ Пожалуйста, введите корректный возраст числом от 12 до 100:")
        return

    await state.update_data(age=int(text))
    await message.answer(
        f"✅ Возраст: **{text} лет**\n\n"
        "👉 **Введите ваш рост в сантиметрах:**\n"
        "_(например: 168)_",
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.height)


@router.message(ProfileForm.height)
async def process_height(message: types.Message, state: FSMContext):
    """Ввод роста."""
    text = message.text.strip().replace(",", ".")
    try:
        val = float(text)
        if not (120 <= val <= 230):
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректный рост от 120 до 230 см:")
        return

    await state.update_data(height=val)
    await message.answer(
        f"✅ Рост: **{val:.0f} см**\n\n"
        "👉 **Введите ваш текущий вес в килограммах:**\n"
        "_(например: 59.5)_",
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.weight)


@router.message(ProfileForm.weight)
async def process_weight(message: types.Message, state: FSMContext):
    """Ввод веса."""
    text = message.text.strip().replace(",", ".")
    try:
        val = float(text)
        if not (30 <= val <= 250):
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректный вес от 30 до 250 кг:")
        return

    await state.update_data(weight=val)
    await message.answer(
        f"✅ Вес: **{val:.1f} кг**\n\n"
        "👉 **Для кого нужно составлять меню и готовить?**\n"
        "_(Бот будет рассчитывать порции и список покупок под этот выбор)_",
        reply_markup=get_persons_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.persons_count)


@router.callback_query(ProfileForm.persons_count, F.data.startswith("persons_"))
async def process_persons(callback: types.CallbackQuery, state: FSMContext):
    """Выбор количества персон."""
    count = int(callback.data.replace("persons_", ""))
    await state.update_data(persons_count=count)
    await callback.answer(f"Выбрано: {count} чел.")

    count_str = "только на меня одну 👩" if count == 1 else f"на {count} чел. 👨‍👩‍👧"
    await callback.message.edit_text(
        f"✅ Формат питания: **{count_str}**\n\n"
        "👉 **Укажите ваш уровень активности:**",
        reply_markup=get_activity_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.activity)


@router.callback_query(ProfileForm.activity, F.data.startswith("act_"))
async def process_activity(callback: types.CallbackQuery, state: FSMContext):
    """Выбор уровня активности."""
    mapping = {
        "act_sedentary": "сидячий / малоподвижный",
        "act_moderate": "умеренная активность",
        "act_high": "высокая активность"
    }
    act_str = mapping.get(callback.data, "умеренная активность")
    await state.update_data(activity=act_str)
    await callback.answer(act_str)

    await callback.message.edit_text(
        f"✅ Активность: **{act_str}**\n\n"
        "👉 **Какова ваша основная цель питания?**",
        reply_markup=get_goal_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.goal)


@router.callback_query(ProfileForm.goal, F.data.startswith("goal_"))
async def process_goal(callback: types.CallbackQuery, state: FSMContext):
    """Выбор цели питания."""
    mapping = {
        "goal_lose": "мягкое снижение веса",
        "goal_maintain": "поддержание формы и тонус",
        "goal_gain": "набор массы / тонус"
    }
    goal_str = mapping.get(callback.data, "поддержание формы")
    await state.update_data(goal=goal_str)
    await callback.answer(goal_str)

    await callback.message.edit_text(
        f"✅ Цель: **{goal_str}**\n\n"
        "👉 **❤️ Какие ваши ЛЮБИМЫЕ продукты, которые вас радуют?**\n"
        "_(Например: «манго, авокадо, пармезан, горький шоколад, креветки, творог»)_\n\n"
        "Бот-нутрициолог обязательно будет регулярно включать их в меню и перекусы для удовольствия без срывов!\n\n"
        "Если нет особых предпочтений — нажмите «Пропустить»:",
        reply_markup=get_skip_keyboard("favorites"),
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.favorite_foods)


@router.callback_query(ProfileForm.favorite_foods, F.data == "skip_favorites")
async def skip_favorites(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск ввода любимых продуктов."""
    await state.update_data(favorite_foods="")
    await callback.answer("Любимые продукты не указаны")
    await ask_cooking_habit(callback.message, state)


@router.message(ProfileForm.favorite_foods)
async def process_favorites_text(message: types.Message, state: FSMContext):
    """Ввод любимых продуктов текстом."""
    fav_text = message.text.strip()
    await state.update_data(favorite_foods=fav_text)
    await message.answer(f"✅ Любимые вкусности зафиксированы: **{fav_text}** ❤️")
    await ask_cooking_habit(message, state)


async def ask_cooking_habit(message: types.Message, state: FSMContext):
    """Запрос формата готовки."""
    await message.answer(
        "👉 **🥘 Как вы привыкли готовить?**\n"
        "_(Чтобы меню и рецепты идеально вписывались в ваш ритм жизни)_",
        reply_markup=get_cooking_habit_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.cooking_habit)


@router.callback_query(ProfileForm.cooking_habit, F.data.startswith("cookhabit_"))
async def process_cooking_habit(callback: types.CallbackQuery, state: FSMContext):
    """Выбор привычки готовки."""
    habit = "на 2-3 дня вперёд (заготовки)" if "batch" in callback.data else "каждый день свежее"
    await state.update_data(cooking_habit=habit)
    await callback.answer(habit)

    await callback.message.edit_text(
        f"✅ Формат готовки: **{habit}**\n\n"
        "👉 **⏰ Укажите ваш примерный режим питания и приемов пищи:**\n"
        "_(например: «Завтрак 08:30, обед 13:30, перекус 16:30, ужин 19:30»)_\n\n"
        "Если график плавающий — нажмите «Пропустить»:",
        reply_markup=get_skip_keyboard("schedule"),
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.meal_schedule)


@router.callback_query(ProfileForm.meal_schedule, F.data == "skip_schedule")
async def skip_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск режима питания."""
    await state.update_data(meal_schedule="")
    await callback.answer("Режим дня свободный")
    await ask_allergies(callback.message, state)


@router.message(ProfileForm.meal_schedule)
async def process_schedule_text(message: types.Message, state: FSMContext):
    """Ввод режима питания текстом."""
    text = message.text.strip()
    await state.update_data(meal_schedule=text)
    await message.answer(f"✅ Режим питания сохранен: **{text}** ⏰")
    await ask_allergies(message, state)


async def ask_allergies(message: types.Message, state: FSMContext):
    """Запрос аллергий."""
    await message.answer(
        "👉 **Есть ли у вас аллергии или непереносимости продуктов?**\n"
        "_(например: лактоза, глютен, арахис, морепродукты)_\n\n"
        "Если аллергий нет — нажмите кнопку «Пропустить шаг»:",
        reply_markup=get_skip_keyboard("allergies"),
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.allergies)


@router.callback_query(ProfileForm.allergies, F.data == "skip_allergies")
async def skip_allergies(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск ввода аллергий."""
    await state.update_data(allergies="нет")
    await callback.answer("Аллергии отсутствуют")
    await ask_disliked(callback.message, state)


@router.message(ProfileForm.allergies)
async def process_allergies_text(message: types.Message, state: FSMContext):
    """Ввод аллергий текстом."""
    text = message.text.strip()
    await state.update_data(allergies=text)
    await message.answer(f"✅ Аллергии учтены: **{text}**")
    await ask_disliked(message, state)


async def ask_disliked(message: types.Message, state: FSMContext):
    """Запрос стоп-листа."""
    await message.answer(
        "👉 **Укажите нелюбимые продукты (СТОП-ЛИСТ):**\n"
        "_(продукты, которые вы терпеть не можете и бот никогда не добавит в меню, "
        "например: кинза, варёный лук, печень, сельдерей)_\n\n"
        "Если ограничений нет — нажмите «Пропустить шаг»:",
        reply_markup=get_skip_keyboard("disliked"),
        parse_mode="Markdown"
    )
    await state.set_state(ProfileForm.disliked_foods)


@router.callback_query(ProfileForm.disliked_foods, F.data == "skip_disliked")
async def skip_disliked(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск стоп-листа."""
    await state.update_data(disliked_foods="нет")
    await callback.answer("Стоп-лист пуст")
    await finish_profile_setup(callback.from_user.id, callback.message, state)


@router.message(ProfileForm.disliked_foods)
async def process_disliked_text(message: types.Message, state: FSMContext):
    """Ввод стоп-листа текстом."""
    await state.update_data(disliked_foods=message.text.strip())
    await finish_profile_setup(message.from_user.id, message, state)


async def finish_profile_setup(user_id: int, message: types.Message, state: FSMContext):
    """Завершение анкеты, расчет КБЖУ, запись в БД и вывод карточки."""
    data = await state.get_data()
    await state.clear()

    # Расчет целевых калорий и БЖУ
    targets = calculate_bmr_and_targets(
        gender=data.get("gender", "женский"),
        age=data.get("age", 30),
        height=data.get("height", 165),
        weight=data.get("weight", 60),
        activity=data.get("activity", "умеренная"),
        goal=data.get("goal", "поддержание")
    )
    data.update(targets)
    data["is_onboarded"] = 1

    # Сохраняем в базу данных
    await save_user_profile(user_id, data)

    # Выводим красивую карточку
    summary_text = (
        "🎉 **Отлично! Ваш персональный профиль нутрициолога готов!**\n\n"
        + format_profile_card(data)
    )

    await message.answer(
        summary_text,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


# ==================== БЫСТРОЕ ТОЧЕЧНОЕ РЕДАКТИРОВАНИЕ ЦЕЛИ ====================

@router.callback_query(F.data == "edit_goal")
async def start_edit_goal(callback: types.CallbackQuery, state: FSMContext):
    """Быстрая смена цели из меню профиля."""
    await callback.answer()
    await state.set_state(QuickEditForm.waiting_for_goal)
    await callback.message.answer(
        "🎯 **Выберите новую цель питания:**\n\n"
        "Суточная норма калорий и БЖУ пересчитается автоматически, "
        "а все ваши аллергии, стоп-лист и любимые продукты сохранятся!",
        reply_markup=get_change_goal_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(QuickEditForm.waiting_for_goal, F.data.startswith("setgoal_"))
async def process_quick_goal(callback: types.CallbackQuery, state: FSMContext):
    """Сохранение новой цели и моментальный пересчет КБЖУ."""
    await state.clear()
    mapping = {
        "setgoal_lose": "мягкое снижение веса",
        "setgoal_maintain": "поддержание формы и тонус",
        "setgoal_gain": "набор массы / тонус"
    }
    new_goal = mapping.get(callback.data, "поддержание формы")
    profile = await get_user_profile(callback.from_user.id)
    if not profile:
        await callback.answer("Профиль не найден")
        return

    # Пересчитываем целевое КБЖУ с новой целью
    targets = calculate_bmr_and_targets(
        gender=profile.get("gender", "женский"),
        age=profile.get("age", 30),
        height=profile.get("height", 165),
        weight=profile.get("weight", 60),
        activity=profile.get("activity", "умеренная"),
        goal=new_goal
    )

    updates = {"goal": new_goal}
    updates.update(targets)
    await update_profile_fields(callback.from_user.id, updates)
    await callback.answer(f"Цель изменена: {new_goal}")

    updated_profile = await get_user_profile(callback.from_user.id)
    await callback.message.edit_text(
        f"✅ **Цель успешно обновлена на «{new_goal.capitalize()}»!**\n\n"
        + format_profile_card(updated_profile),
        reply_markup=get_profile_actions_keyboard(),
        parse_mode="Markdown"
    )


# ==================== БЫСТРАЯ СМЕНА ПОЛА ====================

@router.callback_query(F.data == "edit_gender")
async def start_edit_gender(callback: types.CallbackQuery):
    """Выбор нового пола из меню профиля."""
    await callback.answer()
    await callback.message.answer(
        "🚻 **Выберите ваш пол:**\n\n"
        "Суточная норма калорий и БЖУ будет автоматически пересчитана "
        "по формуле Миффлина — Сан Жеора с учетом мужской или женской физиологии.\n"
        "Все остальные параметры (цель, любимые продукты, аллергии, стоп-лист) сохранятся!",
        reply_markup=get_gender_change_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("setgender_"))
async def process_quick_gender(callback: types.CallbackQuery, state: FSMContext):
    """Сохранение нового пола и автоматический пересчет КБЖУ."""
    await state.clear()
    new_gender = "женский" if "female" in callback.data else "мужской"
    profile = await get_user_profile(callback.from_user.id)
    if not profile:
        await callback.answer("Профиль не найден")
        return

    # Пересчитываем целевое КБЖУ с новым полом
    targets = calculate_bmr_and_targets(
        gender=new_gender,
        age=profile.get("age", 30),
        height=profile.get("height", 165),
        weight=profile.get("weight", 60),
        activity=profile.get("activity", "умеренная"),
        goal=profile.get("goal", "поддержание")
    )

    updates = {"gender": new_gender}
    updates.update(targets)
    await update_profile_fields(callback.from_user.id, updates)
    await callback.answer(f"Пол изменен: {new_gender}")

    updated_profile = await get_user_profile(callback.from_user.id)
    icon = "👨" if new_gender == "мужской" else "👩"
    await callback.message.edit_text(
        f"✅ **Пол успешно изменен на {icon} {new_gender.capitalize()}!**\n"
        f"Норма КБЖУ пересчитана.\n\n"
        + format_profile_card(updated_profile),
        reply_markup=get_profile_actions_keyboard(),
        parse_mode="Markdown"
    )


# ==================== БЫСТРОЕ ОБНОВЛЕНИЕ ТЕКУЩЕГО ВЕСА ====================

@router.callback_query(F.data == "edit_weight")
async def start_edit_weight(callback: types.CallbackQuery, state: FSMContext):
    """Запрос нового веса."""
    await callback.answer()
    profile = await get_user_profile(callback.from_user.id)
    cur_weight = profile.get("weight", 60.0) if profile else 60.0

    await state.set_state(QuickEditForm.waiting_for_weight)
    await callback.message.answer(
        f"⚖️ **Обновление текущего веса**\n\n"
        f"Текущее значение: **{cur_weight:.1f} кг**\n\n"
        "👉 Введите ваш новый вес в килограммах (например: `58.2`):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )


@router.message(QuickEditForm.waiting_for_weight)
async def process_quick_weight(message: types.Message, state: FSMContext):
    """Сохранение нового веса и автоматический пересчет КБЖУ."""
    text = message.text.strip().replace(",", ".")
    try:
        new_weight = float(text)
        if not (30 <= new_weight <= 250):
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректный вес от 30 до 250 кг:")
        return

    await state.clear()
    profile = await get_user_profile(message.from_user.id)
    if not profile:
        await message.answer("Профиль не найден.")
        return

    # Пересчитываем целевое КБЖУ с новым весом
    targets = calculate_bmr_and_targets(
        gender=profile.get("gender", "женский"),
        age=profile.get("age", 30),
        height=profile.get("height", 165),
        weight=new_weight,
        activity=profile.get("activity", "умеренная"),
        goal=profile.get("goal", "поддержание")
    )

    updates = {"weight": new_weight}
    updates.update(targets)
    await update_profile_fields(message.from_user.id, updates)

    # Записываем в историю взвешиваний и рассчитываем динамику
    await database.add_weight_entry(message.from_user.id, new_weight)
    dynamics = await database.get_weight_dynamics(message.from_user.id)
    dyn_text = ""
    if dynamics.get("has_data") and dynamics.get("count", 0) > 1:
        tot_diff = dynamics.get("total_diff", 0.0)
        sign = "+" if tot_diff > 0 else ""
        dyn_text = f"\n📉 **Динамика веса:** _{sign}{tot_diff:.1f} кг_ (старт: {dynamics['start_weight']:.1f} кг ➡️ сейчас: {new_weight:.1f} кг)\n"

    updated_profile = await get_user_profile(message.from_user.id)
    await message.answer(
        f"✅ **Вес обновлен: {new_weight:.1f} кг!** Норма КБЖУ пересчитана.{dyn_text}\n\n"
        + format_profile_card(updated_profile),
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


# ==================== БЫСТРОЕ РЕДАКТИРОВАНИЕ ЛЮБИМЫХ ПРОДУКТОВ ====================

@router.callback_query(F.data == "edit_favorites")
async def start_edit_favorites(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование любимых продуктов."""
    await callback.answer()
    profile = await get_user_profile(callback.from_user.id)
    current = profile.get("favorite_foods", "").strip() if profile else ""
    current_str = current if current else "пока не указаны"

    await state.set_state(QuickEditForm.waiting_for_favorites)
    await callback.message.answer(
        f"❤️ **Любимые вкусности (для радости и десертов)**\n\n"
        f"Текущий список: _{current_str}_\n\n"
        "✍️ Напишите через запятую продукты, которые вы обожаете "
        "_(например: «манго, пармезан, темный шоколад, креветки, авокадо»)_.\n\n"
        "Бот будет с удовольствием регулярно включать их в меню!",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )


@router.message(QuickEditForm.waiting_for_favorites)
async def save_quick_favorites(message: types.Message, state: FSMContext):
    """Сохранение любимых продуктов."""
    new_favs = message.text.strip()
    await state.clear()
    await update_profile_fields(message.from_user.id, {"favorite_foods": new_favs})

    profile = await get_user_profile(message.from_user.id)
    await message.answer(
        f"✅ **Любимые продукты сохранены:**\n❤️ _{new_favs}_\n\n"
        "Теперь они будут регулярно радовать вас в рационах и перекусах!",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


# ==================== БЫСТРОЕ РЕДАКТИРОВАНИЕ ПРИВЫЧКИ ГОТОВКИ И РЕЖИМА ====================

@router.callback_query(F.data == "edit_cooking_habit")
async def start_edit_cooking_habit(callback: types.CallbackQuery):
    """Выбор формата готовки."""
    await callback.answer()
    await callback.message.answer(
        "🥘 **Выберите удобный для вас формат готовки:**",
        reply_markup=get_cooking_habit_keyboard()
    )


@router.callback_query(F.data.startswith("cookhabit_"))
async def save_quick_cooking_habit(callback: types.CallbackQuery, state: FSMContext):
    """Сохранение выбранного формата готовки."""
    # Если мы внутри анкеты, этот хендлер не должен перехватывать
    if await state.get_state() is not None:
        return

    habit = "на 2-3 дня вперёд (заготовки)" if "batch" in callback.data else "каждый день свежее"
    await update_profile_fields(callback.from_user.id, {"cooking_habit": habit})
    await callback.answer(f"Сохранено: {habit}")

    await callback.message.edit_text(
        f"✅ Формат готовки обновлен: **{habit}**!\n"
        "Меню на неделю будет подстраиваться под эту частоту приготовления.",
        parse_mode="Markdown"
    )


# ==================== БЫСТРОЕ ИЗМЕНЕНИЕ ПЕРСОН ====================

@router.callback_query(F.data == "change_persons")
async def quick_change_persons(callback: types.CallbackQuery):
    """Быстрая смена количества персон из меню профиля."""
    await callback.answer()
    await callback.message.answer(
        "🍽️ **Выберите новый формат приготовления блюд:**",
        reply_markup=get_persons_keyboard()
    )


@router.callback_query(F.data.startswith("persons_"))
async def save_quick_persons(callback: types.CallbackQuery, state: FSMContext):
    """Сохранение выбранного количества персон вне анкеты."""
    if await state.get_state() is not None:
        return

    count = int(callback.data.replace("persons_", ""))
    await update_profile_fields(callback.from_user.id, {"persons_count": count})
    await callback.answer(f"Сохранено: на {count} чел.")

    count_str = "только на меня одну 👩" if count == 1 else f"на {count} чел. 👨‍👩‍👧"
    await callback.message.edit_text(
        f"✅ Формат приготовления обновлен: **{count_str}**!\n"
        "Теперь меню и рецепты будут рассчитываться на указанное число людей.",
        parse_mode="Markdown"
    )


# ==================== БЫСТРОЕ РЕДАКТИРОВАНИЕ СТОП-ЛИСТА ====================

@router.callback_query(F.data == "edit_disliked")
async def start_edit_disliked(callback: types.CallbackQuery, state: FSMContext):
    """Начало быстрого редактирования стоп-листа."""
    await callback.answer()
    profile = await get_user_profile(callback.from_user.id)
    current = profile.get("disliked_foods", "").strip() if profile else ""
    current_str = current if current else "нет"

    await state.set_state(QuickEditForm.waiting_for_disliked)
    await callback.message.answer(
        f"🚫 **Редактирование стоп-листа (нелюбимые продукты)**\n\n"
        f"Текущие исключения: **{current_str}**\n\n"
        "✍️ Напишите в ответном сообщении продукты через запятую, которые вы не любите "
        "_(например: «кинза, вареный лук, печень, сельдерей»)_.\n\n"
        "Либо нажмите кнопку ниже, чтобы полностью очистить стоп-лист:",
        reply_markup=get_stoplist_edit_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(QuickEditForm.waiting_for_disliked, F.data == "clear_disliked")
async def clear_disliked_callback(callback: types.CallbackQuery, state: FSMContext):
    """Очистка стоп-листа по кнопке."""
    await state.clear()
    await update_profile_fields(callback.from_user.id, {"disliked_foods": "нет"})
    await callback.answer("Стоп-лист очищен")
    await callback.message.edit_text(
        "✅ **Стоп-лист полностью очищен!**\n"
        "Теперь бот может использовать любые полезные продукты без вкусовых ограничений.",
        parse_mode="Markdown"
    )


@router.message(QuickEditForm.waiting_for_disliked)
async def save_quick_disliked_message(message: types.Message, state: FSMContext):
    """Сохранение нового стоп-листа из текста."""
    new_disliked = message.text.strip()
    await state.clear()
    await update_profile_fields(message.from_user.id, {"disliked_foods": new_disliked})
    await message.answer(
        f"✅ **Стоп-лист обновлен:**\n🚫 _{new_disliked}_\n\n"
        "Бот будет строго исключать эти продукты из всех меню, рецептов и перекусов!",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


# ==================== БЫСТРОЕ РЕДАКТИРОВАНИЕ АЛЛЕРГИЙ ====================

@router.callback_query(F.data == "edit_allergies")
async def start_edit_allergies(callback: types.CallbackQuery, state: FSMContext):
    """Начало быстрого редактирования аллергий."""
    await callback.answer()
    profile = await get_user_profile(callback.from_user.id)
    current = profile.get("allergies", "").strip() if profile else ""
    current_str = current if current else "нет"

    await state.set_state(QuickEditForm.waiting_for_allergies)
    await callback.message.answer(
        f"⚠️ **Редактирование аллергий и непереносимостей**\n\n"
        f"Текущие ограничения: **{current_str}**\n\n"
        "✍️ Напишите в ответном сообщении ваши аллергены через запятую "
        "_(например: «лактоза, арахис, морепродукты, глютен»)_.\n\n"
        "Либо нажмите кнопку ниже, если аллергий больше нет:",
        reply_markup=get_allergies_edit_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(QuickEditForm.waiting_for_allergies, F.data == "clear_allergies")
async def clear_allergies_callback(callback: types.CallbackQuery, state: FSMContext):
    """Очистка аллергий по кнопке."""
    await state.clear()
    await update_profile_fields(callback.from_user.id, {"allergies": "нет"})
    await callback.answer("Аллергии очищены")
    await callback.message.edit_text(
        "✅ **Список аллергий очищен!**",
        parse_mode="Markdown"
    )


@router.message(QuickEditForm.waiting_for_allergies)
async def save_quick_allergies_message(message: types.Message, state: FSMContext):
    """Сохранение новых аллергий из текста."""
    new_allergies = message.text.strip()
    await state.clear()
    await update_profile_fields(message.from_user.id, {"allergies": new_allergies})
    await message.answer(
        f"✅ **Аллергии обновлены:**\n⚠️ _{new_allergies}_\n\n"
        "Бот ни при каких обстоятельствах не добавит эти продукты в ваше питание!",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


# ==================== ОТМЕНА РЕДАКТИРОВАНИЯ ====================

@router.callback_query(F.data == "cancel_edit")
async def cancel_quick_edit(callback: types.CallbackQuery, state: FSMContext):
    """Отмена быстрого редактирования параметров."""
    await state.clear()
    await callback.answer("Редактирование отменено")
    profile = await get_user_profile(callback.from_user.id)
    if profile:
        await callback.message.edit_text(
            format_profile_card(profile),
            reply_markup=get_profile_actions_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text("Редактирование отменено.")
