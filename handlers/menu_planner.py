"""
Обработчик составления сбалансированного меню на неделю со списком покупок,
меню на день с быстрой заменой блюд, и сценария «Семейный ужин — разные тарелки».
"""

import re
from typing import Dict, List, Any
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from database import get_user_profile
from states import MenuForm, DayMenuForm, FamilyDinnerForm, ReplaceMealForm
from keyboards import (
    get_main_keyboard,
    get_cancel_keyboard,
    get_save_favorite_keyboard,
    get_day_menu_actions_keyboard,
    get_interactive_shopping_keyboard,
    get_meal_variant_choice_keyboard,
    get_meal_type_log_keyboard
)
from handlers.kbzhu_calc import LAST_CALCULATED_MEALS
import llm_service

router = Router()

# Хранилище списков покупок для интерактивного чеклиста: user_id -> List[Dict[str, Any]]
CURRENT_SHOPPING_LISTS: Dict[int, List[Dict[str, Any]]] = {}

# Хранилище предложенных замен блюд: user_id -> Dict[str, Any]
PENDING_MEAL_REPLACEMENTS: Dict[int, Dict[str, Any]] = {}


def extract_shopping_list_items(menu_text: str) -> List[str]:
    """Извлекает пункты списка покупок из сгенерированного меню на день или на неделю."""
    items = []
    in_shopping_section = False
    for line in menu_text.splitlines():
        line_clean = line.strip()
        lower_line = line_clean.lower()
        if "список покупок" in lower_line or "покупки" in lower_line or "купить" in lower_line:
            in_shopping_section = True
            continue
        if in_shopping_section:
            if (line_clean.startswith("#") and "покуп" not in lower_line and "отдел" not in lower_line) or "пожелани" in lower_line or "приятного" in lower_line:
                break
            match = re.match(r"^[-*•–—\d\.]+\s*(.+)$", line_clean)
            if match:
                item_text = match.group(1).strip()
                # Исключаем заголовки отделов типа "🥦 Овощи, фрукты:"
                if item_text and not item_text.endswith(":") and len(item_text) > 2:
                    items.append(item_text)
    return items


def format_shopping_share_text(items: List[Dict[str, Any]]) -> str:
    """Форматирует список покупок в красивый текст для быстрой пересылки супругу/супруге."""
    lines = ["🛒 Список покупок от «Пищеблока»:\n"]
    for it in items:
        status = "✅ " if it.get("checked") else "▫️ "
        lines.append(f"{status}{it.get('name')}")
    lines.append("\n🥑 Составлено персональным семейным шеф-поваром.")
    return "\n".join(lines)


async def send_interactive_shopping_list(message: types.Message, menu_text: str, title: str = "на день"):
    """Извлекает и отправляет интерактивный список покупок с кнопками-чекбоксами."""
    items = extract_shopping_list_items(menu_text)
    if not items:
        for line in menu_text.splitlines():
            clean = line.strip()
            if clean.startswith(("- ", "• ", "* ")) and len(clean) > 3:
                items.append(clean.lstrip("-•* "))

    items = items[:25]
    if items:
        user_id = message.from_user.id
        CURRENT_SHOPPING_LISTS[user_id] = [
            {"name": it, "checked": False} for it in items
        ]
        share_text = format_shopping_share_text(CURRENT_SHOPPING_LISTS[user_id])
        kb = get_interactive_shopping_keyboard(CURRENT_SHOPPING_LISTS[user_id], share_text=share_text)
        items_preview = "\n".join([f"▫️ {it['name']}" for it in CURRENT_SHOPPING_LISTS[user_id]])
        await message.answer(
            f"🛒 **Интерактивный список покупок {title}:**\n\n"
            f"{items_preview}\n\n"
            "• Нажимайте на продукты ниже, чтобы отмечать купленное прямо в Telegram (`🔘` ➡️ `🟢`).\n"
            "• Нажмите **«📤 Переслать список»**, чтобы в 1 клик отправить готовый чек-лист супругу/супруге!",
            reply_markup=kb,
            parse_mode="Markdown"
        )


# ==================== МЕНЮ НА ДЕНЬ ====================

@router.message(F.text == "☀️ Меню на день 🥗")
@router.message(Command("daymenu"))
async def start_day_menu_planning(message: types.Message, state: FSMContext):
    """Старт составления меню на один день."""
    profile = await get_user_profile(message.from_user.id)
    if not profile or not profile.get("is_onboarded"):
        await message.answer(
            "⚠️ Сначала заполните параметры в разделе **👤 Мой профиль и КБЖУ**, "
            "чтобы меню учитывало ваш рост, вес, цели, аллергии и размер порций!",
            reply_markup=get_main_keyboard()
        )
        return

    await message.answer(
        "☀️ **Составление сбалансированного меню на 1 день** 🥗\n\n"
        "Есть ли у вас особые пожелания на сегодня?\n"
        "_(Например: «лёгкий ужин с рыбой», «завтрак с творогом», «быстрый обед на работу» или просто отправьте «-»)_",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(DayMenuForm.waiting_for_wishes)


@router.message(DayMenuForm.waiting_for_wishes)
async def process_day_menu_generation(message: types.Message, state: FSMContext):
    """Генерация рациона на день."""
    user_wishes = message.text.strip()
    if user_wishes in ["-", "нет", "без пожеланий", "стандартно"]:
        user_wishes = ""

    await state.clear()
    profile = await get_user_profile(message.from_user.id)

    status_msg = await message.answer(
        "🍳 Составляю идеальный рацион на день с точными граммовками порций для весов... ⏳",
        reply_markup=get_main_keyboard()
    )
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        menu_text = await llm_service.generate_day_menu(profile, user_wishes)
        await status_msg.delete()

        chunks = [menu_text[i:i + 4000] for i in range(0, len(menu_text), 4000)]
        for i, chunk in enumerate(chunks):
            kb = get_day_menu_actions_keyboard() if i == len(chunks) - 1 else None
            try:
                await message.answer(chunk, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await message.answer(chunk, reply_markup=kb, parse_mode=None)

        # Отправляем интерактивный список покупок на день
        await send_interactive_shopping_list(message, menu_text, title="на день")

    except Exception as e:
        await message.answer(
            f"⚠️ Ошибка при формировании меню на день: {e}\n"
            "Пожалуйста, попробуйте снова через несколько минут.",
            reply_markup=get_main_keyboard(),
            parse_mode=None
        )


# ==================== ЗАМЕНА БЛЮДА В МЕНЮ ====================

def extract_replacement_variants(text: str, meal_type: str = "Прием") -> Dict[str, Dict[str, Any]]:
    """
    Детерминированно извлекает Вариант 1 и Вариант 2 из ответа шефа по замене блюда.
    Возвращает словарь: { "1": { "dish_name": ..., "calories": ..., "protein": ..., "fat": ..., "carbs": ... }, "2": ... }
    """
    res = {
        "1": {"dish_name": f"{meal_type}: Вариант 1", "calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0},
        "2": {"dish_name": f"{meal_type}: Вариант 2", "calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    }
    pos_v1 = re.search(r"Вариант\s*1", text, re.IGNORECASE)
    pos_v2 = re.search(r"Вариант\s*2", text, re.IGNORECASE)
    var1_text = text[pos_v1.start():pos_v2.start()] if pos_v1 and pos_v2 else (text[pos_v1.start():] if pos_v1 else "")
    var2_text = text[pos_v2.start():] if pos_v2 else ""

    for key, v_text in [("1", var1_text), ("2", var2_text)]:
        if not v_text:
            continue
        nm = re.search(r"Вариант\s*[12][\.\s:]*[«\"]?([^»\"\n]+)[»\"]?", v_text, re.IGNORECASE)
        if nm:
            clean_n = nm.group(1).strip()
            clean_n = re.sub(r"^[«\"]+|[»\"]+$", "", clean_n)
            res[key]["dish_name"] = clean_n[:50]
        cals_m = re.search(r"[~≈]?\s*(\d+(?:[\.,]\d+)?)\s*ккал", v_text)
        if cals_m:
            try:
                res[key]["calories"] = float(cals_m.group(1).replace(",", "."))
            except Exception:
                pass
        b_m = re.search(r"(?:[Бб]елки?|Б)[:\s]*[~≈]?\s*(\d+(?:[\.,]\d+)?)\s*г", v_text)
        if b_m:
            try:
                res[key]["protein"] = float(b_m.group(1).replace(",", "."))
            except Exception:
                pass
        zh_m = re.search(r"(?:[Жж]иры?|Ж)[:\s]*[~≈]?\s*(\d+(?:[\.,]\d+)?)\s*г", v_text)
        if zh_m:
            try:
                res[key]["fat"] = float(zh_m.group(1).replace(",", "."))
            except Exception:
                pass
        u_m = re.search(r"(?:[Уу]глеводы?|У)[:\s]*[~≈]?\s*(\d+(?:[\.,]\d+)?)\s*г", v_text)
        if u_m:
            try:
                res[key]["carbs"] = float(u_m.group(1).replace(",", "."))
            except Exception:
                pass

    return res


@router.callback_query(F.data.startswith("repmeal_"))
async def handle_meal_replacement(callback: types.CallbackQuery, state: FSMContext):
    """Быстрая замена блюда в меню по кнопке с выбором варианта."""
    meal_type = callback.data.replace("repmeal_", "")
    await callback.answer(f"Подбираю замену для: {meal_type}...")
    profile = await get_user_profile(callback.from_user.id)
    if not profile:
        await callback.message.answer("⚠️ Сначала заполните профиль.")
        return

    status_msg = await callback.message.answer(
        f"🍳 Шеф подбирает 2 отличные альтернативы для приема **{meal_type}** "
        f"с точным сохранением суточного КБЖУ и граммовок... ⏳",
        parse_mode="Markdown"
    )
    await callback.bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")

    try:
        replacement_text = await llm_service.replace_single_meal(profile, meal_type)
        await status_msg.delete()

        # Извлекаем Вариант 1 и Вариант 2 для быстрого выбора
        variants = extract_replacement_variants(replacement_text, meal_type)
        PENDING_MEAL_REPLACEMENTS[callback.from_user.id] = {
            "meal_type": meal_type,
            "variants": variants,
            "full_text": replacement_text
        }

        chunks = [replacement_text[i:i + 4000] for i in range(0, len(replacement_text), 4000)]
        choice_kb = get_meal_variant_choice_keyboard(meal_type)
        for i, chunk in enumerate(chunks):
            kb = choice_kb if i == len(chunks) - 1 else None
            try:
                await callback.message.answer(chunk, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await callback.message.answer(chunk, reply_markup=kb, parse_mode=None)

        await state.set_state(ReplaceMealForm.waiting_for_variant_choice)
        await state.update_data(meal_type=meal_type)

    except Exception as e:
        await callback.message.answer(
            f"⚠️ Не удалось подобрать замену: {e}",
            parse_mode=None
        )


async def apply_meal_variant_choice(
    user_id: int,
    message_target: types.Message,
    choice_key: str,
    state: FSMContext,
    callback: types.CallbackQuery = None
):
    """Применяет выбранный вариант блюда (1 или 2), сохраняет в LAST_CALCULATED_MEALS и предлагает занести в дневник."""
    await state.clear()
    pending = PENDING_MEAL_REPLACEMENTS.get(user_id)
    if not pending:
        if callback:
            await callback.answer("Сессия выбора устарела. Запросите замену заново.", show_alert=True)
        else:
            await message_target.answer("⚠️ Сессия выбора варианта устарела. Пожалуйста, нажмите замену блюда заново.")
        return

    meal_type = pending.get("meal_type", "Прием пищи")
    variants = pending.get("variants", {})
    chosen = variants.get(choice_key)

    if not chosen:
        if callback:
            await callback.answer("Вариант не найден", show_alert=True)
        else:
            await message_target.answer("⚠️ Вариант не найден.")
        return

    # Записываем в LAST_CALCULATED_MEALS для мгновенного сохранения в Дневник в 1 клик
    LAST_CALCULATED_MEALS[user_id] = {
        "dish_name": chosen["dish_name"],
        "calories": chosen["calories"],
        "protein": chosen["protein"],
        "fat": chosen["fat"],
        "carbs": chosen["carbs"]
    }

    if callback:
        await callback.answer(f"Выбран Вариант {choice_key}!")

    cals_val = f"{chosen['calories']:.0f}" if chosen['calories'] > 0 else "рассчитано"
    prot_val = f"{chosen['protein']:.1f}г" if chosen['protein'] > 0 else "-"
    fat_val = f"{chosen['fat']:.1f}г" if chosen['fat'] > 0 else "-"
    carbs_val = f"{chosen['carbs']:.1f}г" if chosen['carbs'] > 0 else "-"

    confirm_text = (
        f"✅ **Выбран {meal_type}: Вариант {choice_key}**\n\n"
        f"🍽️ **«{chosen['dish_name']}»**\n"
        f"🔥 **Калории:** ~{cals_val} ккал\n"
        f"🥩 **Б:** {prot_val} | 🥑 **Ж:** {fat_val} | 🍞 **У:** {carbs_val}\n\n"
        f"👉 **Занести это блюдо в Дневник питания прямо сейчас?**\n"
        f"Нажмите кнопку нужного приема пищи ниже 👇"
    )
    log_kb = get_meal_type_log_keyboard()
    await message_target.answer(confirm_text, reply_markup=log_kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("selvar_"))
async def process_select_variant_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка нажатия инлайн-кнопок 'Выбрать Вариант 1 / 2'."""
    parts = callback.data.split("_")
    choice_key = parts[2] if len(parts) >= 3 else "1"
    await apply_meal_variant_choice(
        user_id=callback.from_user.id,
        message_target=callback.message,
        choice_key=choice_key,
        state=state,
        callback=callback
    )


@router.message(ReplaceMealForm.waiting_for_variant_choice)
async def process_select_variant_text(message: types.Message, state: FSMContext):
    """Обработка текстового выбора ('вариант 1 выбираю', '1', 'первый', '2', 'второй')."""
    text = message.text.strip().lower()

    # Если пользователь нажал системную кнопку или команду отмены
    if text in ["❌ отмена / главное меню", "/cancel", "отмена", "стоп", "назад"]:
        await state.clear()
        await message.answer("Выбор варианта отменен.", reply_markup=get_main_keyboard())
        return

    # Определение выбранного варианта
    choice_key = "1"
    if "2" in text or "втор" in text:
        choice_key = "2"
    elif "1" in text or "перв" in text or "один" in text:
        choice_key = "1"
    else:
        choice_key = "1"

    await apply_meal_variant_choice(
        user_id=message.from_user.id,
        message_target=message,
        choice_key=choice_key,
        state=state
    )


# ==================== МЕНЮ НА НЕДЕЛЮ И ИНТЕРАКТИВНЫЕ ПОКУПКИ ====================

@router.message(F.text == "📅 Меню на неделю 🛒")
@router.message(Command("menu"))
async def start_menu_planning(message: types.Message, state: FSMContext):
    """Старт планирования меню на неделю."""
    profile = await get_user_profile(message.from_user.id)
    if not profile or not profile.get("is_onboarded"):
        await message.answer(
            "⚠️ Сначала заполните параметры в разделе **👤 Мой профиль и КБЖУ**, "
            "чтобы меню учитывало ваш рост, вес, цели, аллергии и размер порций!",
            reply_markup=get_main_keyboard()
        )
        return

    await message.answer(
        "📅 **Составление сбалансированного меню на неделю со списком покупок** 🛒\n\n"
        "Есть ли у вас особые пожелания на эту неделю?\n"
        "_(Например: «больше рыбы», «ужины без духовки», «лёгкие супы в обед» или просто отправьте минус «-»)_",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(MenuForm.waiting_for_wishes)


@router.message(MenuForm.waiting_for_wishes)
async def process_menu_generation(message: types.Message, state: FSMContext):
    """Генерация меню с учетом пожеланий и интерактивный список покупок."""
    user_wishes = message.text.strip()
    if user_wishes in ["-", "нет", "без пожеланий", "стандартно"]:
        user_wishes = ""

    await state.clear()
    profile = await get_user_profile(message.from_user.id)

    status_msg = await message.answer(
        "🥑 Составляю ваше персональное меню на неделю с учетом КБЖУ, полезных перекусов "
        "и формирую список покупок... Это займет около 15-25 секунд ⏳",
        reply_markup=get_main_keyboard()
    )
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        menu_text = await llm_service.generate_weekly_menu(profile, user_wishes)
        await status_msg.delete()

        chunks = [menu_text[i:i + 4000] for i in range(0, len(menu_text), 4000)]
        for i, chunk in enumerate(chunks):
            kb = get_save_favorite_keyboard("menu") if i == len(chunks) - 1 else None
            try:
                await message.answer(chunk, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await message.answer(chunk, reply_markup=kb, parse_mode=None)

        # Отправляем интерактивный список покупок на неделю
        await send_interactive_shopping_list(message, menu_text, title="на неделю")

    except Exception as e:
        await message.answer(
            f"⚠️ Ошибка при формировании меню: {e}\n"
            "Пожалуйста, попробуйте снова через несколько минут.",
            reply_markup=get_main_keyboard(),
            parse_mode=None
        )


@router.callback_query(F.data.startswith("shoptoggle_"))
async def toggle_shopping_item(callback: types.CallbackQuery):
    """Переключение чекбокса купленного продукта."""
    idx = int(callback.data.replace("shoptoggle_", ""))
    user_id = callback.from_user.id
    items = CURRENT_SHOPPING_LISTS.get(user_id, [])
    if 0 <= idx < len(items):
        items[idx]["checked"] = not items[idx]["checked"]
        share_text = format_shopping_share_text(items)
        kb = get_interactive_shopping_keyboard(items, share_text=share_text)
        try:
            await callback.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass
        status_str = "Куплено ✅" if items[idx]["checked"] else "Снята отметка 🔘"
        await callback.answer(f"{items[idx]['name'][:20]}: {status_str}")
    else:
        await callback.answer("Элемент не найден")


@router.callback_query(F.data == "shop_refresh")
async def refresh_shopping_list(callback: types.CallbackQuery):
    """Сброс или обновление интерактивного списка покупок."""
    user_id = callback.from_user.id
    items = CURRENT_SHOPPING_LISTS.get(user_id, [])
    if not items:
        await callback.answer("Список покупок пуст. Сформируйте меню на неделю!")
        return
    share_text = format_shopping_share_text(items)
    kb = get_interactive_shopping_keyboard(items, share_text=share_text)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer("Список покупок обновлен")


@router.callback_query(F.data == "shop_send_clean")
async def send_clean_shopping_list_handler(callback: types.CallbackQuery):
    """Отправка чистого сообщения со списком покупок для пересылки через штатную стрелочку Telegram."""
    user_id = callback.from_user.id
    items = CURRENT_SHOPPING_LISTS.get(user_id, [])
    if not items:
        await callback.answer("Список покупок пуст.", show_alert=True)
        return
    await callback.answer("Готово! Отправлено сообщением ниже.")
    share_text = format_shopping_share_text(items)
    await callback.message.answer(
        f"{share_text}\n\n"
        "👉 _Нажмите стрелочку **«Переслать»** у этого сообщения, чтобы отправить список супругу/супруге!_",
        parse_mode="Markdown"
    )


# ==================== СЕМЕЙНЫЙ УЖИН — РАЗНЫЕ ТАРЕЛКИ ====================

@router.message(F.text == "👨‍👩‍👧 Семейный ужин")
@router.message(Command("family"))
async def start_family_dinner_planning(message: types.Message, state: FSMContext):
    """Старт сценария Семейный ужин — разные тарелки."""
    profile = await get_user_profile(message.from_user.id)
    if not profile or not profile.get("is_onboarded"):
        await message.answer(
            "⚠️ Сначала заполните параметры в разделе **👤 Мой профиль и КБЖУ**, "
            "чтобы шеф знал ваши цели и индивидуальные нормы порций!",
            reply_markup=get_main_keyboard()
        )
        return

    await message.answer(
        "👨‍👩‍👧 **Семейный ужин — разные тарелки** 🍲\n\n"
        "Шеф составит рецепт **одного общего блюда** (готовится в одной посуде), "
        "но с **раздельными граммовками для кухонных весов**:\n\n"
        "👩 **Для Неё:** порция под дефицит/форму, легкость, акцент на клетчатку и нежирный белок.\n"
        "👨 **Для Него:** сытная мужская порция под силу и тонус с повышенным белком и сложными углеводами.\n\n"
        "👉 Напишите, из чего хотите приготовить ужин (например: _«куриное филе с овощами»_, _«рыба с рисом»_) "
        "или просто отправьте **«-»**, чтобы шеф предложил фирменное блюдо:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(FamilyDinnerForm.waiting_for_dish)


@router.message(FamilyDinnerForm.waiting_for_dish)
async def process_family_dinner_generation(message: types.Message, state: FSMContext):
    """Генерация семейного ужина с раздельными тарелками."""
    dish_wishes = message.text.strip()
    if dish_wishes in ["-", "нет", "без пожеланий", "любое", "на твой вкус", "стандартно"]:
        dish_wishes = ""

    await state.clear()
    profile = await get_user_profile(message.from_user.id)

    status_msg = await message.answer(
        "🍳 Шеф рассчитывает идеальные пропорции и раздельные тарелки для весов... ⏳",
        reply_markup=get_main_keyboard()
    )
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        dinner_text = await llm_service.generate_family_split_meal(profile, dish_wishes)
        await status_msg.delete()

        chunks = [dinner_text[i:i + 4000] for i in range(0, len(dinner_text), 4000)]
        for i, chunk in enumerate(chunks):
            kb = get_save_favorite_keyboard("family_dinner") if i == len(chunks) - 1 else None
            try:
                await message.answer(chunk, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await message.answer(chunk, reply_markup=kb, parse_mode=None)

    except Exception as e:
        await message.answer(
            f"⚠️ Ошибка при формировании семейного ужина: {e}\n"
            "Пожалуйста, попробуйте снова через несколько минут.",
            reply_markup=get_main_keyboard(),
            parse_mode=None
        )
