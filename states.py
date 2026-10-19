"""
Модуль состояний FSM для aiogram.
Управляет пошаговыми сценариями: заполнением анкеты, точечным редактированием параметров,
составлением меню, вводом продуктов из холодильника, расчетом КБЖУ и ведением Дневника питания.
"""

from aiogram.fsm.state import State, StatesGroup


class ProfileForm(StatesGroup):
    """Состояния для полной пошаговой анкеты пользователя."""
    gender = State()
    age = State()
    height = State()
    weight = State()
    persons_count = State()
    activity = State()
    goal = State()
    allergies = State()
    disliked_foods = State()
    favorite_foods = State()
    cooking_habit = State()
    meal_schedule = State()


class MenuForm(StatesGroup):
    """Состояние запроса меню на неделю с особыми пожеланиями."""
    waiting_for_wishes = State()


class DayMenuForm(StatesGroup):
    """Состояние запроса меню на один день с особыми пожеланиями."""
    waiting_for_wishes = State()


class FamilyDinnerForm(StatesGroup):
    """Состояние запроса семейного ужина с раздельными тарелками."""
    waiting_for_dish = State()


class FridgeForm(StatesGroup):
    """Состояние ввода продуктов из холодильника."""
    waiting_for_ingredients = State()


class KbzhuForm(StatesGroup):
    """Состояние ввода блюда для расчета КБЖУ."""
    waiting_for_meal_description = State()


class QuickEditForm(StatesGroup):
    """Быстрое точечное редактирование параметров без полного перезаполнения анкеты."""
    waiting_for_goal = State()
    waiting_for_weight = State()
    waiting_for_favorites = State()
    waiting_for_cooking_habit = State()
    waiting_for_meal_schedule = State()
    waiting_for_disliked = State()
    waiting_for_allergies = State()


class FoodDiaryForm(StatesGroup):
    """Состояния для Дневника питания (подсчет съеденного за день)."""
    waiting_for_dish_text = State()
    waiting_for_meal_type = State()


class ReplaceMealForm(StatesGroup):
    """Состояние выбора альтернативного варианта блюда."""
    waiting_for_variant_choice = State()

