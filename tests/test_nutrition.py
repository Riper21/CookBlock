"""Нутрициологическое ядро: Миффлин-Сан Жеор, цели, прогресс-бары, карточки."""

import nutrition

FEMALE = {"gender": "женский", "age": 28, "height": 168.0, "weight": 58.5,
          "activity": "умеренная", "goal": "мягкое снижение веса"}
MALE = {"gender": "мужской", "age": 30, "height": 175.0, "weight": 75.0,
        "activity": "умеренная", "goal": "поддержание"}


def test_bmr_gender_difference():
    """Мужчина (+5) vs женщина (-161) при одинаковых данных: разница BMR ровно 166 ккал."""
    same = {"age": 30, "height": 175.0, "weight": 75.0,
            "activity": "умеренная", "goal": "поддержание"}
    m = nutrition.calculate_bmr_and_targets(gender="мужской", **same)
    f = nutrition.calculate_bmr_and_targets(gender="женский", **same)
    assert m["bmr"] - f["bmr"] == 166.0


def test_female_bmr_formula():
    bmr = nutrition.calculate_bmr_and_targets(**FEMALE)["bmr"]
    expected = 10 * 58.5 + 6.25 * 168 - 5 * 28 - 161
    assert round(bmr) == round(expected)


def test_weight_loss_never_below_bmr():
    """Безопасный дефицит: цель не проваливается ниже базового обмена."""
    t = nutrition.calculate_bmr_and_targets(**FEMALE)
    assert t["target_calories"] >= t["bmr"]


def test_maintenance_equals_tdee():
    t = nutrition.calculate_bmr_and_targets(**MALE)
    assert t["target_calories"] == t["tdee"]


def test_protein_per_kg_goal_dependent():
    """Похудение: 1.6 г/кг белка, поддержание: 1.4 г/кг."""
    cut = nutrition.calculate_bmr_and_targets(**FEMALE)
    keep = nutrition.calculate_bmr_and_targets(**MALE)
    assert cut["target_protein"] == round(58.5 * 1.6, 1)
    assert keep["target_protein"] == round(75.0 * 1.4, 1)


def test_progress_bar_half():
    bar = nutrition.render_progress_bar(500, 1000)
    assert "50%" in bar and bar.count("🟩") == 4 and bar.count("⬜") == 4


def test_progress_bar_overfill_warns():
    bar = nutrition.render_progress_bar(1300, 1000)
    assert "⚠️" in bar and "🟧" in bar


def test_progress_bar_zero_target():
    assert "0%" in nutrition.render_progress_bar(100, 0)


def test_profile_card_gender_wording():
    male_card = nutrition.format_profile_card({**MALE, "persons_count": 1})
    female_card = nutrition.format_profile_card({**FEMALE, "persons_count": 1})
    assert "на меня одного 👨" in male_card
    assert "на меня одну 👩" in female_card


def test_profile_card_contains_targets():
    card = nutrition.format_profile_card({**FEMALE, "persons_count": 2,
                                          "target_calories": 1550, "target_protein": 93.5,
                                          "target_fat": 58.5, "target_carbs": 163.0})
    assert "1550" in card and "93.5" in card and "на 2 чел." in card


def test_daily_diary_card_renders_summary():
    profile = {**FEMALE, "target_calories": 1550.0, "target_protein": 93.0,
               "target_fat": 58.5, "target_carbs": 163.0}
    logs = [{"meal_type": "Завтрак", "food_description": "Овсянка 50г, 2 яйца",
             "created_at": "08:30", "calories": 420.0, "protein": 24.0,
             "fat": 14.0, "carbs": 48.0}]
    summary = {"meals_count": 1, "calories": 420.0, "protein": 24.0,
               "fat": 14.0, "carbs": 48.0}
    card = nutrition.format_daily_diary_card(profile, logs, summary, "2026-09-20")
    assert "20.09.2026" in card
    assert "420 / 1550" in card
    assert "Овсянка" in card
    assert "Осталось до вашей нормы" in card


def test_daily_diary_card_overrun_is_kind():
    """Перебор нормы - поддержка, а не нотация."""
    profile = {"target_calories": 1000.0, "target_protein": 50.0,
               "target_fat": 40.0, "target_carbs": 100.0}
    summary = {"meals_count": 3, "calories": 1250.0, "protein": 50.0,
               "fat": 40.0, "carbs": 100.0}
    card = nutrition.format_daily_diary_card(profile, [], summary, "2026-09-20")
    assert "превышена на 250" in card
    assert "Ничего страшного" in card
