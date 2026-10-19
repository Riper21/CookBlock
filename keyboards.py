"""
Модуль клавиатур Telegram (ReplyKeyboardMarkup и InlineKeyboardMarkup).
Обеспечивает навигацию, управление профилем, Дневником питания и избранным.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CopyTextButton
)
from typing import List, Dict, Any


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная постоянная клавиатура бота (зафиксирована внизу)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="☀️ Меню на день 🥗"),
                KeyboardButton(text="📅 Меню на неделю 🛒")
            ],
            [
                KeyboardButton(text="🍳 Рецепт из холодильника"),
                KeyboardButton(text="📊 Рассчитать КБЖУ блюда")
            ],
            [
                KeyboardButton(text="📸 Фото тарелки (Vision)"),
                KeyboardButton(text="🎙️ Голосовой ввод (Whisper)")
            ],
            [
                KeyboardButton(text="📖 Дневник питания 🥑"),
                KeyboardButton(text="👨‍👩‍👧 Семейный ужин")
            ],
            [
                KeyboardButton(text="🍫 SOS: Сладкое / Срыв"),
                KeyboardButton(text="⭐ Моё избранное")
            ],
            [
                KeyboardButton(text="👤 Мой профиль и КБЖУ"),
                KeyboardButton(text="🔄 Сброс диалога")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
        input_field_placeholder="Отправьте фото 📸, голос 🎙️ или выберите раздел..."
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены текущего действия (зафиксирована внизу)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена / Главное меню")]
        ],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False
    )


# ==================== КЛАВИАТУРЫ АНКЕТЫ И ПРОФИЛЯ ====================

def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Выбор пола."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👩 Женский", callback_data="gender_female"),
                InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male")
            ]
        ]
    )


def get_gender_change_keyboard() -> InlineKeyboardMarkup:
    """Быстрая смена пола из меню профиля."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👩 Женский", callback_data="setgender_female"),
                InlineKeyboardButton(text="👨 Мужской", callback_data="setgender_male")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")
            ]
        ]
    )


def get_persons_keyboard() -> InlineKeyboardMarkup:
    """Выбор количества персон."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Индивидуально (1 чел.)", callback_data="persons_1")],
            [InlineKeyboardButton(text="👫 На двоих (2 чел.)", callback_data="persons_2")],
            [InlineKeyboardButton(text="👨‍👩‍👧 На семью (3 чел.)", callback_data="persons_3")],
            [InlineKeyboardButton(text="👨‍👩‍👧‍👦 На большую семью (4+ чел.)", callback_data="persons_4")]
        ]
    )


def get_activity_keyboard() -> InlineKeyboardMarkup:
    """Выбор уровня активности."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛋️ Сидячий (малоподвижный)", callback_data="act_sedentary")],
            [InlineKeyboardButton(text="🚶 Умеренный (прогулки, 1-3 тренировки)", callback_data="act_moderate")],
            [InlineKeyboardButton(text="🏃 Активный (тренировки 4-5 раз в неделю)", callback_data="act_high")]
        ]
    )


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Выбор цели питания в анкете."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🥗 Мягкое снижение веса", callback_data="goal_lose")],
            [InlineKeyboardButton(text="⚖️ Поддержание формы и тонус", callback_data="goal_maintain")],
            [InlineKeyboardButton(text="💪 Набор мышечной массы / тонус", callback_data="goal_gain")]
        ]
    )


def get_change_goal_keyboard() -> InlineKeyboardMarkup:
    """Быстрая смена цели из меню профиля."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🥗 Мягкое снижение веса", callback_data="setgoal_lose")],
            [InlineKeyboardButton(text="⚖️ Поддержание формы и тонус", callback_data="setgoal_maintain")],
            [InlineKeyboardButton(text="💪 Набор мышечной массы / тонус", callback_data="setgoal_gain")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ]
    )


def get_cooking_habit_keyboard() -> InlineKeyboardMarkup:
    """Выбор формата приготовления блюд."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍳 Готовлю каждый день свежее", callback_data="cookhabit_fresh")],
            [InlineKeyboardButton(text="🥘 На 2-3 дня вперёд (заготовки, супы)", callback_data="cookhabit_batch")]
        ]
    )


def get_skip_keyboard(step_name: str) -> InlineKeyboardMarkup:
    """Кнопка пропуска необязательного шага анкеты."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить шаг ➡️", callback_data=f"skip_{step_name}")]
        ]
    )


def get_profile_actions_keyboard() -> InlineKeyboardMarkup:
    """Модульные действия в профиле пользователя."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Изменить цель", callback_data="edit_goal"),
                InlineKeyboardButton(text="⚖️ Обновить вес", callback_data="edit_weight")
            ],
            [
                InlineKeyboardButton(text="🚻 Изменить пол", callback_data="edit_gender"),
                InlineKeyboardButton(text="🍽️ Число персон", callback_data="change_persons")
            ],
            [
                InlineKeyboardButton(text="❤️ Любимые продукты", callback_data="edit_favorites"),
                InlineKeyboardButton(text="🥘 Режим и готовка", callback_data="edit_cooking_habit")
            ],
            [
                InlineKeyboardButton(text="🚫 Стоп-лист", callback_data="edit_disliked"),
                InlineKeyboardButton(text="⚠️ Аллергии", callback_data="edit_allergies")
            ],
            [
                InlineKeyboardButton(text="✏️ Перезаполнить всё", callback_data="edit_full_profile")
            ]
        ]
    )


def get_gender_change_keyboard() -> InlineKeyboardMarkup:
    """Быстрая смена пола из меню профиля."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👩 Женский", callback_data="setgender_female"),
                InlineKeyboardButton(text="👨 Мужской", callback_data="setgender_male")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")
            ]
        ]
    )


def get_stoplist_edit_keyboard() -> InlineKeyboardMarkup:
    """Кнопки при редактировании стоп-листа."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Очистить стоп-лист (нет ограничений)", callback_data="clear_disliked")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ]
    )


def get_allergies_edit_keyboard() -> InlineKeyboardMarkup:
    """Кнопки при редактировании аллергий."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Очистить аллергии (нет аллергий)", callback_data="clear_allergies")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ]
    )


# ==================== КЛАВИАТУРЫ ДНЕВНИКА ПИТАНИЯ ====================

def get_meal_type_log_keyboard() -> InlineKeyboardMarkup:
    """Кнопки под расчетом КБЖУ для записи в Дневник питания в 1 клик."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🍳 В Завтрак", callback_data="logmeal_Завтрак"),
                InlineKeyboardButton(text="🥗 В Обед", callback_data="logmeal_Обед")
            ],
            [
                InlineKeyboardButton(text="🍲 В Ужин", callback_data="logmeal_Ужин"),
                InlineKeyboardButton(text="🍏 В Перекус", callback_data="logmeal_Перекус")
            ],
            [
                InlineKeyboardButton(text="⭐ Сохранить в избранное", callback_data="save_fav_kbzhu")
            ]
        ]
    )


def get_fridge_recipe_keyboard() -> InlineKeyboardMarkup:
    """Кнопки под рецептом из холодильника для записи в Дневник и сохранения."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🍳 В Завтрак", callback_data="logmeal_Завтрак"),
                InlineKeyboardButton(text="🥗 В Обед", callback_data="logmeal_Обед")
            ],
            [
                InlineKeyboardButton(text="🍲 В Ужин", callback_data="logmeal_Ужин"),
                InlineKeyboardButton(text="🍏 В Перекус", callback_data="logmeal_Перекус")
            ],
            [
                InlineKeyboardButton(text="⭐ Сохранить в избранное", callback_data="save_fav_recipe")
            ]
        ]
    )


def get_vision_log_keyboard() -> InlineKeyboardMarkup:
    """Кнопки под распознанным фото блюда для записи в Дневник в 1 клик."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🍳 В Завтрак", callback_data="vlog_Завтрак"),
                InlineKeyboardButton(text="🥗 В Обед", callback_data="vlog_Обед")
            ],
            [
                InlineKeyboardButton(text="🍲 В Ужин", callback_data="vlog_Ужин"),
                InlineKeyboardButton(text="🍏 В Перекус", callback_data="vlog_Перекус")
            ],
            [
                InlineKeyboardButton(text="❌ Не записывать", callback_data="vlog_cancel")
            ]
        ]
    )


def get_food_diary_keyboard(has_logs: bool = False) -> InlineKeyboardMarkup:
    """Кнопки управления Дневником питания."""
    buttons = [
        [
            InlineKeyboardButton(text="➕ Записать приём пищи", callback_data="diary_add_meal"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="diary_refresh")
        ],
        [
            InlineKeyboardButton(text="💡 Что съесть на ужин / перекус?", callback_data="diary_advice")
        ]
    ]
    if has_logs:
        buttons.append([
            InlineKeyboardButton(text="🗑️ Удалить запись", callback_data="diary_delete_menu"),
            InlineKeyboardButton(text="🧹 Очистить за сегодня", callback_data="diary_clear_day")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_delete_food_log_keyboard(logs: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Инлайн-список записей для выбора удаляемого приема пищи."""
    buttons = []
    meal_icons = {"Завтрак": "🍳", "Обед": "🥗", "Ужин": "🍲", "Перекус": "🍏"}
    for item in logs[:10]:
        m_type = item.get("meal_type", "Прием")
        icon = meal_icons.get(m_type, "🍽️")
        desc = item.get("food_description", "")[:20]
        cals = item.get("calories", 0.0)
        btn_text = f"❌ {icon} {m_type}: {desc} (~{cals:.0f} ккал)"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"dellog_{item['id']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в дневник", callback_data="diary_refresh")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== КЛАВИАТУРЫ ИЗБРАННОГО ====================

def get_save_favorite_keyboard(action_tag: str) -> InlineKeyboardMarkup:
    """Кнопка под сообщением LLM для сохранения в избранное."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Сохранить в избранное", callback_data=f"save_fav_{action_tag}")]
        ]
    )


def get_favorites_list_keyboard(favorites: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Список сохраненных записей в избранном."""
    buttons = []
    category_icons = {
        "menu": "📅",
        "daymenu": "☀️",
        "recipe": "🍳",
        "kbzhu": "📊",
        "general": "💡",
        "shopping": "🛒"
    }

    for item in favorites[:15]:
        icon = category_icons.get(item.get("category"), "📌")
        title = item.get("title", "Запись")[:28]
        date_str = item.get("created_at", "")
        btn_text = f"{icon} {title} ({date_str.split()[0] if date_str else ''})"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"fav_view_{item['id']}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_favorite_item_keyboard(fav_id: int, share_url: str = "", share_text: str = "") -> InlineKeyboardMarkup:
    """Кнопки при просмотре отдельной записи избранного."""
    buttons = []
    if share_url or share_text:
        action_row = []
        if share_url:
            action_row.append(InlineKeyboardButton(text="📤 Переслать список", url=share_url))
        if share_text:
            action_row.append(InlineKeyboardButton(text="📋 Скопировать", copy_text=CopyTextButton(text=share_text)))
        if action_row:
            buttons.append(action_row)
    buttons.extend([
        [InlineKeyboardButton(text="🗑️ Удалить из избранного", callback_data=f"fav_del_{fav_id}")],
        [InlineKeyboardButton(text="⬅️ Назад ко всем избранным", callback_data="fav_back_list")]
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ИНТЕРАКТИВНЫЙ СПИСОК ПОКУПОК И МЕНЮ ====================

def get_interactive_shopping_keyboard(items: List[Dict[str, Any]], share_text: str = "") -> InlineKeyboardMarkup:
    """
    Клавиатура интерактивного списка покупок с чек-боксами, пересылкой и копированием.
    items: список элементов [{'name': str, 'checked': bool}]
    """
    import urllib.parse
    buttons = []
    for idx, item in enumerate(items[:20]):
        name = item.get("name", "Продукт")
        checked = item.get("checked", False)
        icon = "🟢" if checked else "🔘"
        # Сокращаем длину текста кнопки при необходимости
        btn_text = f"{icon} {name}"[:36]
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"shoptoggle_{idx}")])

    if share_text:
        encoded_text = urllib.parse.quote(share_text)
        share_url = f"https://t.me/share/url?url=https://t.me&text={encoded_text}"
        buttons.append([
            InlineKeyboardButton(text="📤 Переслать список", url=share_url),
            InlineKeyboardButton(text="📋 Скопировать", copy_text=CopyTextButton(text=share_text))
        ])
        buttons.append([
            InlineKeyboardButton(text="📩 Отдельным сообщением для пересылки", callback_data="shop_send_clean")
        ])

    buttons.append([
        InlineKeyboardButton(text="⭐ Сохранить в избранное", callback_data="save_fav_shopping"),
        InlineKeyboardButton(text="🔄 Обновить список", callback_data="shop_refresh")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_meal_replace_keyboard(meal_type: str) -> InlineKeyboardMarkup:
    """Кнопка под приемом пищи для быстрой замены блюда."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🔄 Заменить {meal_type}", callback_data=f"repmeal_{meal_type}")]
        ]
    )


def get_day_menu_actions_keyboard() -> InlineKeyboardMarkup:
    """Кнопки под меню на день (сохранение и замена блюд)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Заменить Завтрак", callback_data="repmeal_Завтрак"),
                InlineKeyboardButton(text="🔄 Заменить Обед", callback_data="repmeal_Обед")
            ],
            [
                InlineKeyboardButton(text="🔄 Заменить Ужин", callback_data="repmeal_Ужин"),
                InlineKeyboardButton(text="🔄 Заменить Перекус", callback_data="repmeal_Перекус")
            ],
            [
                InlineKeyboardButton(text="⭐ Сохранить в избранное", callback_data="save_fav_daymenu")
            ]
        ]
    )


def get_meal_variant_choice_keyboard(meal_type: str) -> InlineKeyboardMarkup:
    """Кнопки под предложенными альтернативами блюд для быстрого выбора."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🥣 Выбрать Вариант 1", callback_data=f"selvar_{meal_type}_1"),
                InlineKeyboardButton(text="🍳 Выбрать Вариант 2", callback_data=f"selvar_{meal_type}_2")
            ],
            [
                InlineKeyboardButton(text="⭐ Сохранить в избранное", callback_data="save_fav_recipe")
            ]
        ]
    )



