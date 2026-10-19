"""Клавиатуры и UI-слой: главная клавиатура, SOS, Vision-лог, покупки, замена блюд."""

import keyboards


def test_main_keyboard_contains_all_sections():
    kb = keyboards.get_main_keyboard()
    buttons = [btn.text for row in kb.keyboard for btn in row]
    assert "🍫 SOS: Сладкое / Срыв" in buttons
    assert "📸 Фото тарелки (Vision)" in buttons
    assert "🎙️ Голосовой ввод (Whisper)" in buttons


def test_vision_log_keyboard_callbacks():
    cbs = [btn.callback_data for row in keyboards.get_vision_log_keyboard().inline_keyboard for btn in row]
    assert "vlog_Завтрак" in cbs and "vlog_Обед" in cbs and "vlog_cancel" in cbs


def test_gender_change_keyboard():
    cbs = [btn.callback_data for row in keyboards.get_gender_change_keyboard().inline_keyboard for btn in row]
    assert "setgender_male" in cbs and "setgender_female" in cbs


def test_day_menu_replacement_buttons():
    cbs = [btn.callback_data for row in keyboards.get_day_menu_actions_keyboard().inline_keyboard for btn in row]
    for meal in ("Завтрак", "Обед", "Ужин", "Перекус"):
        assert f"repmeal_{meal}" in cbs


def test_interactive_shopping_keyboard_share_and_copy():
    items = [{"name": "Огурцы (500 г)", "checked": False},
             {"name": "Куриное филе (1 кг)", "checked": True}]
    share_text = "Список покупок"
    kb = keyboards.get_interactive_shopping_keyboard(items, share_text=share_text)
    urls = [btn.url for row in kb.inline_keyboard for btn in row if btn.url]
    assert len(urls) == 1 and urls[0].startswith("https://t.me/share/url?url=https://t.me&text=")
    copies = [btn for row in kb.inline_keyboard for btn in row if getattr(btn, "copy_text", None)]
    assert len(copies) == 1 and copies[0].copy_text.text == share_text


def test_meal_variant_choice_keyboard():
    cbs = [btn.callback_data for row in keyboards.get_meal_variant_choice_keyboard("Завтрак").inline_keyboard for btn in row]
    assert "selvar_Завтрак_1" in cbs and "selvar_Завтрак_2" in cbs
