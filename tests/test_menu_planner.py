"""Парсеры меню: список покупок, пересылка, выбор вариантов замены блюд."""

from handlers.menu_planner import (
    extract_replacement_variants,
    extract_shopping_list_items,
    format_shopping_share_text,
)


def test_extract_shopping_list_items():
    menu = "### 🛒 Список покупок на неделю:\n- Томаты (500 г)\n- Творог 5% (400 г)\n\nПриятного аппетита!"
    items = extract_shopping_list_items(menu)
    assert len(items) == 2
    assert "Томаты (500 г)" in items


def test_shopping_share_text_checked_states():
    items = [{"name": "Огурцы (500 г)", "checked": False},
             {"name": "Куриное филе (1 кг)", "checked": True}]
    text = format_shopping_share_text(items)
    assert "▫️ Огурцы" in text
    assert "✅ Куриное филе" in text


def test_extract_replacement_variants():
    sample = """
    ## 🥣 Вариант 1. «Овсянка по-спортивному» с творогом
    - Вес порции: ~430 г
    - КБЖУ порции: ~720 ккал | Б 34 г | Ж 22 г | У 88 г
    ---
    ## 🍳 Вариант 2. «Белковый омлет с сыром»
    - Вес порции: ~500 г
    - КБЖУ порции: ~710 ккал | Б 36 г | Ж 27 г | У 77 г
    """
    variants = extract_replacement_variants(sample, "Завтрак")
    assert variants["1"]["calories"] == 720.0
    assert variants["1"]["protein"] == 34.0
    assert variants["2"]["calories"] == 710.0
    assert "Овсянка" in variants["1"]["dish_name"]
    assert "омлет" in variants["2"]["dish_name"].lower()
