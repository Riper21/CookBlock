"""
Модуль нутрициологических расчетов, экспертных подсказок и оформления карточек.
Формула Миффлина — Сан Жеора, расчет целевого КБЖУ, оформление профиля и Дневника питания.
"""

import random
from typing import Dict, Any, List, Optional
from datetime import datetime


# Банк теплых рандомных пожеланий нутрициолога
MOTIVATIONAL_WISHES = [
    "✨ У тебя всё обязательно получится! Ты делаешь прекрасный шаг к здоровью и лёгкости.",
    "🌱 Ты на верном пути! Помни: забота о себе — это лучшая инвестиция.",
    "🥑 Это отличный выбор для энергии, сияния кожи и отличного самочувствия!",
    "💫 Маленькие шаги в питании дают невероятные результаты в будущем. Горжусь твоим выбором!",
    "🎯 Твой организм обязательно поблагодарит тебя за качественное и сбалансированное топливо!",
    "☀️ Здоровая и вкусная еда — это радость каждого дня, а не ограничения!",
    "🥦 Прекрасный выбор продуктов! Гармония вкуса, пользы и баланса.",
    "🍓 Ты формируешь потрясающие привычки для долголетия и бодрости!",
    "💪 Заботься о себе с удовольствием, каждый полезный приём пищи имеет значение!"
]


def get_random_wish() -> str:
    """Возвращает случайное теплое мотивирующее пожелание."""
    return random.choice(MOTIVATIONAL_WISHES)


def calculate_bmr_and_targets(
    gender: str,
    age: int,
    height: float,
    weight: float,
    activity: str = "умеренная",
    goal: str = "поддержание"
) -> Dict[str, float]:
    """
    Расчет базового обмена веществ (BMR) по формуле Миффлина — Сан Жеора
    и суточной нормы КБЖУ в зависимости от активности и цели.
    """
    # 1. BMR по формуле Миффлина — Сан Жеора
    gender_lower = gender.lower()
    if "муж" in gender_lower:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:  # По умолчанию женский
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # 2. Коэффициент физической активности
    activity_lower = activity.lower()
    if "сидяч" in activity_lower or "миним" in activity_lower:
        coef = 1.2
    elif "активн" in activity_lower or "высок" in activity_lower:
        coef = 1.55
    elif "очень" in activity_lower or "спортсмен" in activity_lower:
        coef = 1.725
    else:  # "умеренная" (1-3 тренировки/прогулки в неделю)
        coef = 1.375

    tdee = bmr * coef

    # 3. Коррекция под цель
    goal_lower = goal.lower()
    if "похуден" in goal_lower or "снижен" in goal_lower:
        target_calories = max(bmr, tdee * 0.85)  # Безопасный дефицит 15%, не ниже BMR
    elif "набор" in goal_lower or "профицит" in goal_lower:
        target_calories = tdee * 1.12  # Профицит 12%
    else:  # Поддержание формы / тонус
        target_calories = tdee

    target_calories = round(target_calories, 0)

    # 4. Расчет целевого БЖУ
    protein_per_kg = 1.6 if "похуден" in goal_lower or "снижен" in goal_lower else 1.4
    protein_g = round(weight * protein_per_kg, 1)

    # Жиры: 1.0 г на кг веса (важно для эндокринной системы, минимум 50г)
    fat_g = round(max(50.0, weight * 1.0), 1)

    # Углеводы: остаток калорий
    consumed_kcal = (protein_g * 4) + (fat_g * 9)
    carbs_kcal = max(0.0, target_calories - consumed_kcal)
    carbs_g = round(carbs_kcal / 4.0, 1)

    return {
        "bmr": round(bmr, 0),
        "tdee": round(tdee, 0),
        "target_calories": target_calories,
        "target_protein": protein_g,
        "target_fat": fat_g,
        "target_carbs": carbs_g
    }


def format_profile_card(user_data: Dict[str, Any]) -> str:
    """Форматирует расширенную карточку профиля для сообщения в Telegram."""
    gender = user_data.get("gender", "женский")
    age = user_data.get("age", 30)
    height = user_data.get("height", 165)
    weight = user_data.get("weight", 60)
    persons_count = user_data.get("persons_count", 1)
    activity = user_data.get("activity", "умеренная")
    goal = user_data.get("goal", "поддержание")
    allergies = user_data.get("allergies", "").strip() or "Нет"
    disliked_foods = user_data.get("disliked_foods", "").strip() or "Нет"
    favorite_foods = user_data.get("favorite_foods", "").strip() or "Не указаны (добавьте для радости)"
    cooking_habit = user_data.get("cooking_habit", "").strip() or "Каждый день свежее"
    meal_schedule = user_data.get("meal_schedule", "").strip() or "Свободный"

    cals = int(user_data.get("target_calories", 1800))
    prot = round(user_data.get("target_protein", 90), 1)
    fat = round(user_data.get("target_fat", 60), 1)
    carbs = round(user_data.get("target_carbs", 220), 1)

    is_male = "муж" in str(gender).lower()
    if persons_count == 1:
        persons_text = "на меня одного 👨" if is_male else "на меня одну 👩"
    else:
        persons_text = f"на {persons_count} чел. 👨‍👩‍👧"

    return (
        "🌿 **Ваш персональный профиль нутрициолога:**\n\n"
        f"• **Пол:** {gender.capitalize()} | **Возраст:** {age} лет\n"
        f"• **Рост:** {height:.0f} см | **Вес:** {weight:.1f} кг\n"
        f"• **Формат готовки:** {persons_text}\n"
        f"• **Активность:** {activity}\n"
        f"• **Цель питания:** 🎯 **{goal.capitalize()}**\n\n"
        f"❤️ **Любимые вкусности (для радости):**\n_{favorite_foods}_\n\n"
        f"🥘 **Привычка готовить:** {cooking_habit}\n"
        f"⏰ **Режим питания:** {meal_schedule}\n\n"
        f"🚫 **Стоп-лист (нелюбимое):** {disliked_foods}\n"
        f"⚠️ **Аллергии:** {allergies}\n\n"
        "🎯 **Ваша индивидуальная суточная норма КБЖУ:**\n"
        f"🔥 **Калории:** ~{cals} ккал\n"
        f"🥩 **Белки:** ~{prot} г (строительный материал мышц и клеток)\n"
        f"🥑 **Жиры:** ~{fat} г (гормональный баланс, здоровье кожи)\n"
        f"🌾 **Углеводы:** ~{carbs} г (энергия и бодрость)\n\n"
        f"_{get_random_wish()}_"
    )


def render_progress_bar(current: float, target: float, length: int = 8) -> str:
    """Генерирует наглядный прогресс-бар нормы."""
    if target <= 0:
        return f"[{'⬜' * length}] 0%"
    ratio = current / target
    percent = int(ratio * 100)

    if ratio > 1.15:
        # Перебор нормы более чем на 15%
        return f"[{'🟧' * length}] {percent}% ⚠️"

    filled = min(length, int(round(ratio * length)))
    empty = length - filled
    bar = "🟩" * filled + "⬜" * empty
    return f"[{bar}] {percent}%"


def format_daily_diary_card(
    profile: Dict[str, Any],
    logs: List[Dict[str, Any]],
    summary: Dict[str, Any],
    log_date: str
) -> str:
    """Формирует наглядный отчет Дневника питания за выбранный день."""
    target_cals = float(profile.get("target_calories", 1800.0))
    target_prot = float(profile.get("target_protein", 90.0))
    target_fat = float(profile.get("target_fat", 60.0))
    target_carbs = float(profile.get("target_carbs", 220.0))

    eaten_cals = float(summary.get("calories", 0.0))
    eaten_prot = float(summary.get("protein", 0.0))
    eaten_fat = float(summary.get("fat", 0.0))
    eaten_carbs = float(summary.get("carbs", 0.0))
    meals_count = int(summary.get("meals_count", 0))

    rem_cals = target_cals - eaten_cals
    rem_prot = target_prot - eaten_prot
    rem_fat = target_fat - eaten_fat
    rem_carbs = target_carbs - eaten_carbs

    # Преобразуем дату в читаемый вид: 20.09.2026
    try:
        dt = datetime.strptime(log_date, "%Y-%m-%d")
        date_formatted = dt.strftime("%d.%m.%Y")
    except Exception:
        date_formatted = log_date

    lines = [
        f"📖 **ДНЕВНИК ПИТАНИЯ ЗА {date_formatted}** 🥑\n",
        f"📊 **Баланс за день ({meals_count} приемов пищи):**",
        f"🔥 **Калории:** {eaten_cals:.0f} / {target_cals:.0f} ккал {render_progress_bar(eaten_cals, target_cals)}",
        f"🥩 **Белки:** {eaten_prot:.1f} / {target_prot:.1f} г {render_progress_bar(eaten_prot, target_prot)}",
        f"🥑 **Жиры:** {eaten_fat:.1f} / {target_fat:.1f} г {render_progress_bar(eaten_fat, target_fat)}",
        f"🌾 **Углеводы:** {eaten_carbs:.1f} / {target_carbs:.1f} г {render_progress_bar(eaten_carbs, target_carbs)}\n"
    ]

    # Блок остатка
    if rem_cals > 50:
        lines.append(
            f"🎯 **Осталось до вашей нормы:**\n"
            f"• Калории: **~{rem_cals:.0f} ккал**\n"
            f"• Б: **~{max(0.0, rem_prot):.1f} г** | Ж: **~{max(0.0, rem_fat):.1f} г** | У: **~{max(0.0, rem_carbs):.1f} г**\n"
        )
    elif rem_cals < -100:
        lines.append(
            f"⚠️ **Норма калорий превышена на {abs(rem_cals):.0f} ккал.** "
            "Ничего страшного! Завтра вернемся в комфортный режим без жестких ограничений.\n"
        )
    else:
        lines.append("🎉 **Идеально! Ваша норма калорий за день точно выполнена!** 🌟\n")

    # Список съеденных блюд
    if logs:
        lines.append("🍽️ **Съедено за день:**")
        meal_icons = {
            "Завтрак": "🍳",
            "Обед": "🥗",
            "Ужин": "🍲",
            "Перекус": "🍏"
        }
        for idx, item in enumerate(logs, 1):
            m_type = item.get("meal_type", "Прием пищи")
            icon = meal_icons.get(m_type, "🍽️")
            time_str = item.get("created_at", "")
            desc = item.get("food_description", "")
            c = item.get("calories", 0.0)
            p = item.get("protein", 0.0)
            f = item.get("fat", 0.0)
            cb = item.get("carbs", 0.0)
            lines.append(
                f"{idx}. {icon} **{m_type}** ({time_str}): _{desc}_\n"
                f"   └ ~{c:.0f} ккал | Б: {p:.1f}г | Ж: {f:.1f}г | У: {cb:.1f}г"
            )
    else:
        lines.append("📝 _Записей на сегодня пока нет. Нажмите «➕ Добавить приём пищи» или рассчитайте блюдо!_")

    lines.append(f"\n_{get_random_wish()}_")
    return "\n".join(lines)
