"""
Модуль взаимодействия с LLM (DeepSeek / OpenAI / Gemini через OpenAI API).
Содержит системные промпты профессионального нутрициолога и шеф-повара,
генерацию меню на день/неделю с учетом любимых продуктов и привычки готовки,
расчет КБЖУ блюд, парсинг для Дневника питания и умные советы по остатку нормы.
"""

import os
import json
import re
import base64
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
import httpx
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, PROXY_URL
from nutrition import get_random_wish
import database

logger = logging.getLogger(__name__)


def get_llm_client() -> OpenAI:
    """Создает клиент OpenAI для вызова DeepSeek или Gemini."""
    if PROXY_URL and PROXY_URL.strip():
        http_client = httpx.Client(proxy=PROXY_URL.strip(), timeout=LLM_TIMEOUT)
        return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, http_client=http_client)
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=LLM_TIMEOUT)


def get_gender_context(gender: str) -> Dict[str, str]:
    """Возвращает морфологический и физиологический контекст в зависимости от пола."""
    is_male = "муж" in str(gender).lower()
    if is_male:
        return {
            "gender_str": "мужской",
            "noun_nom": "подопечный",
            "noun_gen": "подопечного",
            "noun_dat": "подопечному",
            "noun_acc": "подопечного",
            "pronoun_gen": "его",
            "pronoun_dat": "ему",
            "ate_verb": "съел",
            "accent": (
                "Учитывай особенности мужской физиологии: высокая энергоемкость (BMR), "
                "достаточный уровень чистого белка для синтеза мышечной массы (1.6-2.0 г/кг), "
                "полезные жиры, цинк и магний для поддержки тестостерона, плотность и сытность порций."
            )
        }
    else:
        return {
            "gender_str": "женский",
            "noun_nom": "подопечная",
            "noun_gen": "подопечной",
            "noun_dat": "подопечной",
            "noun_acc": "подопечную",
            "pronoun_gen": "её",
            "pronoun_dat": "ей",
            "ate_verb": "съела",
            "accent": (
                "Учитывай особенности женской физиологии: гормональный баланс, мягкий коридор калорий без стресса, "
                "достаточное количество полезных жиров (омега-3, масла, орехи) для здоровья кожи и волос, "
                "легкость усвоения, баланс железа и кальция."
            )
        }


def build_nutritionist_system_prompt(profile: Dict[str, Any]) -> str:
    """Формирует расширенный системный промпт нутрициолога с учетом всех индивидуальных параметров и пола."""
    gender = profile.get("gender", "женский")
    gc = get_gender_context(gender)

    age = profile.get("age", 30)
    height = profile.get("height", 165)
    weight = profile.get("weight", 60)
    persons_count = profile.get("persons_count", 1)
    allergies = profile.get("allergies", "").strip() or "нет"
    disliked = profile.get("disliked_foods", "").strip() or "нет"
    favorite_foods = profile.get("favorite_foods", "").strip() or "не указаны"
    cooking_habit = profile.get("cooking_habit", "").strip() or "каждый день свежее"
    meal_schedule = profile.get("meal_schedule", "").strip() or "свободный"
    goal = profile.get("goal", "поддержание формы")
    target_cals = profile.get("target_calories", 1800)
    target_prot = profile.get("target_protein", 90)
    target_fat = profile.get("target_fat", 60)
    target_carbs = profile.get("target_carbs", 220)

    persons_note = (
        "Готовка ТОЛЬКО НА ОДНОГО ЧЕЛОВЕКА (порции индивидуальные)."
        if persons_count == 1
        else f"Готовка НА {persons_count} ЧЕЛОВЕК (рассчитывай объем блюд и список покупок на {persons_count} порций)."
    )

    cooking_instruction = (
        f"{gc['noun_nom'].capitalize()} предпочитает ГОТОВИТЬ НА 2-3 ДНЯ ВПЕРЁД. "
        "Группируй обеды и ужины блоками на 2 дня подряд (например, приготовить большую порцию супа или запечь птицу с гарниром сразу на пн+вт), "
        "чтобы не приходилось стоять у плиты каждый приём пищи!"
        if "2-3" in cooking_habit
        else f"{gc['noun_nom'].capitalize()} готовит свежие блюда на каждый день."
    )

    return f"""
Ты — профессиональный дипломированный диетолог-нутрициолог и заботливый семейный шеф-повар.
Твоя миссия — составлять здоровое, сбалансированное, безумно вкусное меню из доступных продуктов обычных магазинов, без сложной экзотики и без вреда для бюджета и времени.

ДАННЫЕ КЛИЕНТА ({gc['noun_gen'].upper()}):
• Пол: {gc['gender_str']}, Возраст: {age} лет, Рост: {height} см, Вес: {weight} кг.
• Цель: {goal}.
• Суточная норма: ~{target_cals} ккал (Б: {target_prot}г, Ж: {target_fat}г, У: {target_carbs}г).
• Формат питания: {persons_note}
• 🥘 Привычка готовки: {cooking_instruction}
• ⏰ Режим питания: {meal_schedule}.
• ❤️ ЛЮБИМЫЕ ПРОДУКТЫ (ДЛЯ РАДОСТИ): {favorite_foods}.
  КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО регулярно включай эти любимые продукты в меню, полезные десерты и перекусы! Это гарантирует психологический комфорт и питание без срывов.
• ⚠️ СТРОГО ЗАПРЕЩЕНО (Аллергии/непереносимости): {allergies}. НИКОГДА не предлагай эти продукты!
• 🚫 СТОП-ЛИСТ (нелюбимые продукты): {disliked}. Исключи их из всех блюд и рецептов!
• 💡 ФИЗИОЛОГИЧЕСКИЙ АКЦЕНТ: {gc['accent']}

КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО ПО ВЕСУ ПОРЦИЙ (КУХОННЫЕ ВЕСЫ):
Для КАЖДОГО блюда и перекуса жизненно необходимо знать:
👉 СКОЛЬКО ГРАММ БЛЮДА ПОЛОЖИТЬ СЕБЕ В ТАРЕЛКУ (вес готовой порции в граммах)!
Поэтому для каждого блюда ВСЕГДА пиши:
1. Рекомендуемый вес порции в граммах (например: «Вес порции: 280 г»).
2. КБЖУ этой конкретной порции (сколько калорий и БЖУ клиент получит, съев эту тарелку).
3. Справочно: КБЖУ на 100 г блюда.
4. В конце каждого дня пиши «ИТОГО ЗА ДЕНЬ: ~ХХХХ ккал (Б: ХХг, Ж: ХХг, У: ХХг)» — сумма приемов пищи должна точно соответствовать суточной норме {gc['noun_gen']}!

ПРАВИЛА И СТИЛЬ ОТВЕТА:
1. Забота, поддержка и доброжелательность: будь тактичным экспертом, поддерживай и вдохновляй.
2. Обращайся к человеку строго в грамматическом роде его пола ({'мужской род: ты съел, готов, силен' if gc['gender_str'] == 'мужской' else 'женский род: ты съела, готова, прекрасна'}).
3. В конце каждого ответа ОБЯЗАТЕЛЬНО добавляй короткое рандомное теплое пожелание в курсиве (например: *«У тебя всё получится! ✨»*, *«Ты на верном пути 🌱»*, *«Это отличный выбор! 🥑»*).
4. Доступность: все продукты должны продаваться в обычном супермаркете у дома (Пятерочка, Магнит, Перекресток).
5. Подписи к перекусам: всегда поясняй вес перекуса в граммах, какой дефицит он закрывает (клетчатка, омега-3, витамин C, магний) и чем он полезен для здоровья.
"""


async def generate_day_menu(profile: Dict[str, Any], extra_wishes: str = "") -> str:
    """Генерация сбалансированного меню на 1 день с граммовками порций, КБЖУ и списком покупок."""
    client = get_llm_client()
    system_prompt = build_nutritionist_system_prompt(profile)
    persons_count = profile.get("persons_count", 1)

    user_prompt = f"""
Составь персональный сбалансированный рацион НА ОДИН ДЕНЬ (Завтрак, Обед, Ужин, Перекус) с учетом моих параметров, любимых продуктов и целей.
Количество персон: {persons_count}.
Дополнительные пожелания: {extra_wishes if extra_wishes else "нет, сделай вкусно, сытно, с любимыми продуктами и сбалансированно"}.

ТРЕБОВАНИЯ К ОФОРМЛЕНИЮ:
1. Подробно распиши каждый прием пищи с понятным быстрым рецептом:
   - 🍳 Завтрак: Название блюда + краткий рецепт приготовления
     • ⚖️ Вес готовой порции: ХХХ г (КБЖУ порции: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
     • (на 100 г блюда: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
   - 🥗 Обед: Название блюда + краткий рецепт приготовления
     • ⚖️ Вес готовой порции: ХХХ г (КБЖУ порции: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
     • (на 100 г блюда: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
   - 🍲 Ужин: Название легкого ужина + краткий рецепт приготовления
     • ⚖️ Вес готовой порции: ХХХ г (КБЖУ порции: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
     • (на 100 г блюда: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
   - 🍏 Перекус: Название полезного перекуса (включи любимые вкусности, если уместно)
     • ⚖️ Вес: ХХХ г (~ХХХ ккал / Б: Х г / Ж: Х г / У: Х г)
     • 💡 Польза: какой параметр закрывает (клетчатка, омега-3, витамины) и чем полезен.

2. 📊 ИТОГО ЗА ДЕНЬ:
   • Суммарно за день: ~ХХХХ ккал | Б: ХХ г | Ж: ХХ г | У: ХХ г (должно точно укладываться в индивидуальную норму подопечной!).
   • Оценка рациона от нутрициолога.

3. 🛒 СПИСОК ПОКУПОК НА ДЕНЬ:
   Компактный список того, что купить в обычном магазине для этого дня.

4. В самом конце добавь теплое мотивационное пожелание.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content


async def generate_weekly_menu(profile: Dict[str, Any], extra_wishes: str = "") -> str:
    """Генерация сбалансированного меню на неделю со списком покупок и учетом формата готовки."""
    client = get_llm_client()
    system_prompt = build_nutritionist_system_prompt(profile)
    persons_count = profile.get("persons_count", 1)

    user_prompt = f"""
Составь персональный план питания (меню на неделю с понедельника по воскресенье) с учетом моих параметров, любимых продуктов, привычки готовки и целей.
Количество персон: {persons_count}.
Дополнительные пожелания: {extra_wishes if extra_wishes else "нет, сделай разнообразно, сбалансированно, вкусно и практично"}.

ТРЕБОВАНИЯ К ОФОРМЛЕНИЮ КАЖДОГО ДНЯ (Понедельник — Воскресенье):
Для каждого приема пищи (Завтрак, Обед, Ужин, Перекус) ОБЯЗАТЕЛЬНО укажи:
- 🍳 Завтрак: Название блюда
  • ⚖️ Вес порции: ХХХ г (КБЖУ порции: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
  • (на 100 г блюда: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
- 🥗 Обед: Название блюда
  • ⚖️ Вес порции: ХХХ г (КБЖУ порции: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
  • (на 100 г блюда: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
- 🍲 Ужин: Название блюда
  • ⚖️ Вес порции: ХХХ г (КБЖУ порции: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
  • (на 100 г блюда: ~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г)
- 🍏 Перекус: Название продукта
  • ⚖️ Вес: ХХХ г (~ХХ ккал / Б: Х г / Ж: Х г / У: Х г)
  • 💡 Польза: какой параметр закрывает и чем полезен.
- 📊 ИТОГО ЗА ДЕНЬ: ~ХХХХ ккал | Б: ХХ г | Ж: ХХ г | У: ХХ г (должно точно сходиться с суточной нормой!).

2. УЧЕТ ГОТОВКИ: Если в профиле указано готовить на 2-3 дня — сгруппируй обеды/ужины блоками на пару дней (например: суп на вт+ср, запеканка на чт+пт).
3. В самом конце составь СВОДНЫЙ СПИСОК ПОКУПОК на неделю, разбитый по отделам супермаркета:
   🥦 Овощи, фрукты и зелень
   🥩 Мясо, птица, рыба, яйца
   🥛 Молочные продукты
   🍝 Бакалея, крупы и масла
   🧂 Приправы и прочее
4. В самом конце добавь теплое пожелание.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content


async def generate_fridge_recipe(profile: Dict[str, Any], available_products: str) -> str:
    """Генерация рецептов из имеющихся продуктов с точным весом порции в граммах и КБЖУ."""
    client = get_llm_client()
    system_prompt = build_nutritionist_system_prompt(profile)
    persons_count = profile.get("persons_count", 1)

    user_prompt = f"""
У меня есть следующие продукты в холодильнике/шкафу:
{available_products}

Придумай 1-2 вкусных, полезных блюда из этого набора (можно использовать базовые соль, масло, специи).
Количество персон: {persons_count}.

ДЛЯ КАЖДОГО РЕЦЕПТА ОБЯЗАТЕЛЬНО УКАЖИ:
1. Аппетитное название блюда
2. Список ингредиентов с точными граммовками (на {persons_count} чел.)
3. ⚖️ Вес готовой порции на 1 человека в граммах (сколько положить в тарелку)
4. КБЖУ этой порции (~ХХХ ккал / Б: ХХ г / Ж: ХХ г / У: ХХ г) + справочно КБЖУ на 100 г блюда
5. Пошаговый простой рецепт приготовления (максимум 4-5 понятных шагов)
6. Нутрициологическая польза блюда
7. В конце добавь мотивационное пожелание.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content


async def calculate_dish_kbzhu(profile: Dict[str, Any], meal_description: str) -> str:
    """
    Расчет КБЖУ по описанию блюда в формате подопечной:
    - Разбор по ингредиентам с весом и ккал/100г
    - Подписи по клетчатке/витаминам/пользе
    - Блок ИТОГО
    """
    client = get_llm_client()
    system_prompt = build_nutritionist_system_prompt(profile)

    user_prompt = f"""
Вот описание моего блюда / приема пищи:
\"\"\"{meal_description}\"\"\"

Рассчитай точное КБЖУ.
ОБЯЗАТЕЛЬНО используй СТРОГО следующий формат (как в моих дневниках питания):

📊 Расчет КБЖУ (название приема пищи или блюда):

• Название ингредиента 1 (вес в г): ~Х ккал / Б: Х,Х г / Ж: Х,Х г / У: Х,Х г (из расчета ХХ ккал/100 г)
• Название ингредиента 2 (вес в г): ~Х ккал / Б: Х,Х г / Ж: Х,Х г / У: Х,Х г (из расчета ХХ ккал/100 г)
...
• (Если есть перекус или полезный акцент): Клетчатка: ~X,X г
• (Если есть витамины): Витамин / минерал: чем полезен для поддержки здоровья

ИТОГО:

• Калории: ~ХХХ ккал
• Белки: ~ХХ,Х г
• Жиры: ~ХХ,Х г
• Углеводы: ~ХХ,Х г

(В конце 1-2 предложения с оценкой нутрициолога и рандомным теплым пожеланием).
Если точные граммовки мной не указаны, оцени стандартную порцию и укажи в скобках граммы.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.3
    )
    return response.choices[0].message.content


def extract_kbzhu_from_calc_result(calc_text: str, fallback_dish_name: str = "Блюдо") -> Dict[str, Any]:
    """
    Детерминированно извлекает точные калории, БЖУ и название блюда
    напрямую из текстового отчета шефа (блока 'ИТОГО').
    Исключает рассинхрон между сообщением на экране и записью в Дневник питания.
    """
    if not calc_text:
        return {
            "dish_name": fallback_dish_name,
            "calories": 0.0,
            "protein": 0.0,
            "fat": 0.0,
            "carbs": 0.0
        }

    # 1. Извлечение названия блюда
    dish_name = ""
    dish_match = re.search(r"(?:[Бб]людо|[Рр]ецепт):\s*[«\"]([^»\"\n]+)[»\"]", calc_text)
    if dish_match:
        dish_name = dish_match.group(1).strip()
    else:
        calc_name_match = re.search(r"Расчет КБЖУ\s*\(([^)\n]+)\)", calc_text, re.IGNORECASE)
        if calc_name_match:
            dish_name = calc_name_match.group(1).strip()

    if not dish_name:
        dish_name = fallback_dish_name if fallback_dish_name else "Прием пищи"

    # Ограничиваем длину названия
    dish_name = dish_name[:50].strip()

    # 2. Поиск секции ИТОГО
    cals = 0.0
    prot = 0.0
    fat = 0.0
    carbs = 0.0

    total_section = calc_text
    total_pos = calc_text.find("ИТОГО")
    if total_pos != -1:
        total_section = calc_text[total_pos:]

    cals_match = re.search(r"(?:[Кк]алории|[Кк]кал)[^\d]*[~≈]?\s*(\d+(?:[\.,]\d+)?)", total_section)
    prot_match = re.search(r"(?:[Бб]елки|[Бб]елок|Б:)[^\d]*[~≈]?\s*(\d+(?:[\.,]\d+)?)", total_section)
    fat_match = re.search(r"(?:[Жж]иры|[Жж]ир|Ж:)[^\d]*[~≈]?\s*(\d+(?:[\.,]\d+)?)", total_section)
    carbs_match = re.search(r"(?:[Уу]глеводы|[Уу]глевод|У:)[^\d]*[~≈]?\s*(\d+(?:[\.,]\d+)?)", total_section)

    if cals_match:
        try:
            cals = float(cals_match.group(1).replace(",", "."))
        except ValueError:
            cals = 0.0

    if prot_match:
        try:
            prot = float(prot_match.group(1).replace(",", "."))
        except ValueError:
            prot = 0.0

    if fat_match:
        try:
            fat = float(fat_match.group(1).replace(",", "."))
        except ValueError:
            fat = 0.0

    if carbs_match:
        try:
            carbs = float(carbs_match.group(1).replace(",", "."))
        except ValueError:
            carbs = 0.0

    return {
        "dish_name": dish_name,
        "calories": round(cals, 1),
        "protein": round(prot, 1),
        "fat": round(fat, 1),
        "carbs": round(carbs, 1)
    }


async def parse_meal_kbzhu(meal_text: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Структурированное извлечение КБЖУ из текста приема пищи для автоматической записи в Дневник.
    Возвращает dict: {"dish_name": str, "calories": float, "protein": float, "fat": float, "carbs": float, "text": str}
    """
    client = get_llm_client()

    prompt = f"""
Пользователь записал, что съел:
\"{meal_text}\"

Определи состав, примерный вес (если не указан — стандартная порция) и рассчитай суммарное КБЖУ.
Верни ответ СТРОГО в формате JSON без какого-либо дополнительного текста, без кавычек ```json:
{{
  "dish_name": "Краткое название блюда (до 30 символов)",
  "calories": 350.0,
  "protein": 18.5,
  "fat": 12.0,
  "carbs": 42.0,
  "short_comment": "1 короткая фраза нутрициолога о пользе блюда"
}}
"""

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        content = response.choices[0].message.content.strip()
        # Очистка от возможных ```json оберток
        clean_json = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        clean_json = re.sub(r"\s*```$", "", clean_json)
        data = json.loads(clean_json)

        return {
            "dish_name": str(data.get("dish_name", meal_text[:30])),
            "calories": float(data.get("calories", 0.0)),
            "protein": float(data.get("protein", 0.0)),
            "fat": float(data.get("fat", 0.0)),
            "carbs": float(data.get("carbs", 0.0)),
            "short_comment": str(data.get("short_comment", "Отличный прием пищи!"))
        }
    except Exception:
        # Запасной вариант при сбое парсинга
        return {
            "dish_name": meal_text[:30],
            "calories": 250.0,
            "protein": 10.0,
            "fat": 8.0,
            "carbs": 30.0,
            "short_comment": "Прием пищи учтен в дневнике!"
        }


async def generate_remaining_day_advice(
    profile: Dict[str, Any],
    remaining: Dict[str, float],
    eaten_summary: Dict[str, Any],
    logs: List[Dict[str, Any]]
) -> str:
    """Генерация персонального совета нутрициолога: что съесть на ужин/перекус исходя из остатка нормы."""
    client = get_llm_client()
    gender = profile.get("gender", "женский")
    gc = get_gender_context(gender)
    system_prompt = build_nutritionist_system_prompt(profile)

    eaten_cals = eaten_summary.get("calories", 0)
    rem_cals = remaining.get("calories", 0)
    rem_p = remaining.get("protein", 0)
    rem_f = remaining.get("fat", 0)
    rem_c = remaining.get("carbs", 0)

    eaten_items_text = ", ".join([f"{item.get('meal_type')}: {item.get('food_description')}" for item in logs]) if logs else "записей нет"

    user_prompt = f"""
Сегодня {gc['noun_nom']} уже {gc['ate_verb']} (~{eaten_cals:.0f} ккал):
{eaten_items_text}

ДО {gc['pronoun_gen'].upper()} СУТОЧНОЙ НОРМЫ ОСТАЛОСЬ:
• Калории: ~{rem_cals:.0f} ккал
• Белки: ~{rem_p:.1f} г
• Жиры: ~{rem_f:.1f} г
• Углеводы: ~{rem_c:.1f} г

ЗАДАЧА:
Дай теплый экспертный совет нутрициолога:
1. Оцени баланс уже съеденного за день (чего достаточно, а что нужно добрать — например, дефицит белка или клетчатки).
2. Предложи 2 конкретных вкусных варианта завершения дня (легкий ужин или полезный перекус), которые идеально закроют этот остаток без перебора калорий.
3. Если уместно, используй {gc['pronoun_gen']} любимые вкусности ({profile.get('favorite_foods', 'вкусная здоровая еда')}).
4. Напиши вес порции в граммах и КБЖУ для предложенных вариантов.
5. Закончи душевным мотивирующим пожеланием.
"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content


async def general_nutrition_chat(user_id: int, profile: Dict[str, Any], user_message: str) -> str:
    """Свободный диалог с нутрициологом с сохранением контекста в постоянную БД SQLite."""
    client = get_llm_client()
    system_prompt = build_nutritionist_system_prompt(profile)

    recent_history = await database.get_recent_chat_messages(user_id, limit=8)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(recent_history)
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7
    )

    reply = response.choices[0].message.content

    await database.add_chat_message(user_id, "user", user_message)
    await database.add_chat_message(user_id, "assistant", reply)

    return reply


async def reset_chat_history(user_id: int):
    """Сброс истории диалога для пользователя в БД."""
    await database.clear_chat_messages(user_id)


def parse_vision_response(content: str) -> Dict[str, Any]:
    """
    Надежный двухконтурный парсер ответа DeepSeek Flash Vision:
    1. Попытка разобрать JSON (если модель сгенерировала валидный JSON-блок).
    2. Извлечение структурированного шаблона по регулярным выражениям.
    """
    content = content.strip()

    # Контур 1: Проверка на валидный JSON
    clean_json = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
    clean_json = re.sub(r"\s*```$", "", clean_json).strip()
    start_idx = clean_json.find("{")
    end_idx = clean_json.rfind("}")
    if start_idx != -1 and end_idx != -1:
        try:
            data = json.loads(clean_json[start_idx:end_idx + 1])
            return {
                "is_food": bool(data.get("is_food", True)),
                "dish_name": str(data.get("dish_name", "Блюдо по фото")),
                "weight_g": float(data.get("weight_g", 0.0)),
                "calories": float(data.get("calories", 0.0)),
                "protein": float(data.get("protein", 0.0)),
                "fat": float(data.get("fat", 0.0)),
                "carbs": float(data.get("carbs", 0.0)),
                "components": data.get("components", []),
                "comment": str(data.get("comment", "Блюдо распознано по фото."))
            }
        except Exception:
            pass

    # Контур 2: Структурированный шаблон
    # 2.1. Проверка на "НЕ ЕДА"
    non_food_match = re.search(r"[•\*\-]?\s*(?:НЕ\s*ЕДА|НЕ_ЕДА|НЕЕДА):\s*(.+)", content, re.IGNORECASE | re.DOTALL)
    if non_food_match:
        comment = non_food_match.group(1).strip()
        return {
            "is_food": False,
            "dish_name": "Не еда",
            "weight_g": 0.0,
            "calories": 0.0,
            "protein": 0.0,
            "fat": 0.0,
            "carbs": 0.0,
            "components": [],
            "comment": comment
        }

    # 2.2. Извлечение названия блюда
    dish_match = re.search(r"[•\*\-]?\s*(?:Блюдо|Название):\s*(.+)", content, re.IGNORECASE)
    dish_name = dish_match.group(1).split("\n")[0].strip(" *`_#") if dish_match else "Блюдо по фото"

    # 2.3. Вес порции (число или диапазон вида 400–450 г)
    weight_g = 0.0
    weight_range = re.search(r"[•\*\-]?\s*Вес(?:\s+порции)?:\s*[~≈]?\s*(\d+)\s*[–\-—]\s*(\d+)", content, re.IGNORECASE)
    if weight_range:
        weight_g = (float(weight_range.group(1)) + float(weight_range.group(2))) / 2
    else:
        weight_match = re.search(r"[•\*\-]?\s*Вес(?:\s+порции)?:\s*[~≈]?\s*(\d+(?:[\.,]\d+)?)", content, re.IGNORECASE)
        if weight_match:
            weight_g = float(weight_match.group(1).replace(",", "."))

    # 2.4. КБЖУ
    calories = 0.0
    protein = 0.0
    fat = 0.0
    carbs = 0.0

    kbzhu_line_match = re.search(r"[•\*\-]?\s*КБЖУ:[^\n]+", content, re.IGNORECASE)
    kbzhu_scope = kbzhu_line_match.group(0) if kbzhu_line_match else content

    cal_range = re.search(r"(?:КБЖУ|Калории|Ккал)[^|\n\d]*[~≈]?\s*(\d+)\s*[–\-—]\s*(\d+)", kbzhu_scope, re.IGNORECASE)
    if cal_range:
        calories = (float(cal_range.group(1)) + float(cal_range.group(2))) / 2
    else:
        cal_match = re.search(r"(?:КБЖУ|Калории|Ккал)[^|\n\d]*[~≈]?\s*(\d+(?:[\.,]\d+)?)", kbzhu_scope, re.IGNORECASE)
        if cal_match:
            calories = float(cal_match.group(1).replace(",", "."))

    p_match = re.search(r"(?<![А-Яа-яA-Za-z])(?:Б:|Белки:)[^\d]*[~≈]?\s*(\d+(?:[\.,]\d+)?)", kbzhu_scope, re.IGNORECASE)
    if p_match:
        protein = float(p_match.group(1).replace(",", "."))

    f_match = re.search(r"(?<![А-Яа-яA-Za-z])(?:Ж:|Жиры:)[^\d]*[~≈]?\s*(\d+(?:[\.,]\d+)?)", kbzhu_scope, re.IGNORECASE)
    if f_match:
        fat = float(f_match.group(1).replace(",", "."))

    c_match = re.search(r"(?<![А-Яа-яA-Za-z])(?:У:|Углеводы:)[^\d]*[~≈]?\s*(\d+(?:[\.,]\d+)?)", kbzhu_scope, re.IGNORECASE)
    if c_match:
        carbs = float(c_match.group(1).replace(",", "."))

    # 2.5. Состав
    components = []
    comp_match = re.search(r"[•\*\-]?\s*Состав:\s*(.+)", content, re.IGNORECASE)
    if comp_match:
        comp_str = comp_match.group(1).split("\n")[0].strip()
        items = [i.strip() for i in re.split(r"[,;]", comp_str) if i.strip()]
        for item in items:
            components.append({"name": item, "weight_g": 0.0, "calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0})

    # 2.6. Польза и совет нутрициолога
    comment_parts = []
    polza_match = re.search(r"[•\*\-]?\s*Польза:\s*(.+)", content, re.IGNORECASE)
    if polza_match:
        comment_parts.append(polza_match.group(1).split("\n")[0].strip())

    sovet_match = re.search(r"[•\*\-]?\s*Совет(?:\s+нутрициолога)?:\s*(.+)", content, re.IGNORECASE)
    if sovet_match:
        comment_parts.append(sovet_match.group(1).split("\n")[0].strip())

    comment = " ".join(comment_parts) if comment_parts else "Блюдо распознано по фото."

    # Если калории не были распознаны, но известен вес
    if calories == 0.0 and weight_g > 0:
        calories = round(weight_g * 1.2, 1)

    return {
        "is_food": True,
        "dish_name": str(dish_name[:50]),
        "weight_g": round(weight_g, 1),
        "calories": round(calories, 1),
        "protein": round(protein, 1),
        "fat": round(fat, 1),
        "carbs": round(carbs, 1),
        "components": components,
        "comment": comment
    }


async def analyze_food_photo(image_bytes: bytes, profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Мультимодальный анализ фото тарелки через DeepSeek Flash (Vision).
    Распознает блюдо, состав, граммовку, рассчитывает КБЖУ и возвращает структурированный словарь:
    {
        "is_food": bool,
        "dish_name": str,
        "weight_g": float,
        "calories": float,
        "protein": float,
        "fat": float,
        "carbs": float,
        "components": [
            {"name": str, "weight_g": float, "calories": float, "protein": float, "fat": float, "carbs": float}
        ],
        "comment": str
    }
    """
    client = get_llm_client()
    b64_data = base64.b64encode(image_bytes).decode("utf-8")

    allergies = profile.get("allergies", "нет")
    goal = profile.get("goal", "поддержание формы")
    target_cals = profile.get("target_calories", 1800)

    gender = profile.get("gender", "женский")
    gc = get_gender_context(gender)

    prompt = f"""Ты — дипломированный нутрициолог и заботливый шеф-повар.
Внимательно изучи изображение.
ДАННЫЕ КЛИЕНТА ({gc['noun_gen'].upper()}): Пол: {gc['gender_str']}, Цель: {goal}, Суточная норма: ~{target_cals} ккал, Аллергии: {allergies}.
• Физиологический фокус: {gc['accent']}

ПРАВИЛА ОЦЕНКИ ВЕСА И КБЖУ (МАСШТАБ И ДИЕТИЧЕСКИЙ ПРОФИЛЬ):
1. МАСШТАБ: Обязательно ищи в кадре предметы-ориентиры (столовая ложка/вилка ~18-20 см, ширина черпака ложки ~4 см, пальцы, край тарелки). Оценивай реальные габариты кусков еды относительно приборов.
2. ГАРНИРЫ ПРИ КОНТРОЛЕ ВЕСА: Не завышай вес плотных гарниров (рис, гречка, макароны). На домашней диетической тарелке порция риса/крупы обычно составляет всего 50–80 г (2–3 столовые ложки), а не ресторанные 150–200 г! Оценивай реальную толщину слоя.
3. БЕЛОК И ОВОЩИ: Оценивай размер кусочков курицы/рыбы/мяса и овощей относительно ложки (стандартная домашняя порция птицы/мяса 100–130 г).
4. ЖИРЫ: Не завышай жиры, если блюдо запеченное или тушеное и визуально не блестит от обильного масла.

Если на фото НЕ еда (предмет, текст, логотип, человек без еды, интерьер):
• НЕ ЕДА: [опиши что на картинке и вежливо попроси сфотографировать тарелку с едой]

Если на фото ЕДА (готовое блюдо, перекус, напиток, продукты):
Оформи ответ строго по пунктам:
• Блюдо: [Название блюда]
• Вес порции: ~[число или диапазон] г
• КБЖУ: ~[число] ккал | Б: [число] г | Ж: [число] г | У: [число] г
• Состав: [ингредиенты блюда через запятую с примерными граммовками]
• Польза: [1-2 предложения о нутрициологической ценности и балансе блюда]
• Совет нутрициолога: [рекомендация для цели: {goal}]
"""

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}}
                ]
            }],
            max_tokens=4096,
            temperature=0.6
        )
        content = response.choices[0].message.content or ""
        return parse_vision_response(content)
    except Exception as e:
        err_text = str(e).lower()
        # Модель без Vision: понятное объяснение вместо «не удалось разобрать снимок»
        if any(marker in err_text for marker in ("image", "vision", "multimodal", "not support", "unsupported", "invalid_request_error")):
            return {
                "is_food": False,
                "dish_name": "Модель без поддержки фото",
                "weight_g": 0.0,
                "calories": 0.0,
                "protein": 0.0,
                "fat": 0.0,
                "carbs": 0.0,
                "components": [],
                "comment": (
                    "Ваша модель нейросети (LLM_MODEL в файле .env) не умеет анализировать изображения. "
                    "Фото-разбор блюд работает только с мультимодальной (Vision) моделью. "
                    "Все текстовые функции бота работают в полном объеме: попробуйте кнопку «📊 Рассчитать КБЖУ»."
                )
            }
        logger.error(f"Ошибка вызова LLM Vision: {e}", exc_info=True)
        return {
            "is_food": False,
            "dish_name": "Ошибка распознавания",
            "weight_g": 0.0,
            "calories": 0.0,
            "protein": 0.0,
            "fat": 0.0,
            "carbs": 0.0,
            "components": [],
            "comment": "Не удалось разобрать снимок. Пожалуйста, убедитесь, что в кадре тарелка с едой и сделайте фото ближе."
        }


async def generate_sweet_sos(profile: Dict[str, Any]) -> str:
    """
    Генерация экспресс-помощи нутрициолога при тяге к сладкому или случившемся срыве:
    1. Психологическая поддержка без чувства вины (срывы бывают у каждого, это физиология).
    2. 3 экспресс-десерта за 2-3 минуты из подручных продуктов с учетом favorite_foods.
    3. Конкретный алгоритм компенсации, если уже съеден магазинный десерт/шоколад.
    """
    client = get_llm_client()
    gender = profile.get("gender", "женский")
    gc = get_gender_context(gender)
    system_prompt = build_nutritionist_system_prompt(profile)
    fav = profile.get("favorite_foods", "шоколад, ягоды, фрукты")

    user_prompt = f"""
У {gc['noun_gen']} критическая ситуация: сильная тяга к сладкому / риск срыва или уже {gc['ate_verb']} десерт!
{gc['pronoun_gen'].capitalize()} любимые продукты для радости: {fav}.

Помоги как заботливый, мудрый и профессиональный нутрициолог:

1. 🫂 ПСИХОЛОГИЧЕСКАЯ ПОДДЕРЖКА (БЕЗ ВИНО И САМОЕДСТВА):
   Коротко, душевно и тепло объясни, почему желание сладкого — это абсолютно нормальная реакция организма (усталость, падение глюкозы, стресс, гормоны), и один десерт НИКОГДА не перечеркивает результаты.

2. 🍨 3 ЭКСПРЕСС-ДЕСЕРТА ЗА 2-3 МИНУТЫ (ЗАКРЫТЬ ТЯГУ ПРЯМО СЕЙЧАС):
   Предложи 3 моментальных рецепта из простых продуктов (творог, какао, банан, яблоко, орехи, ягоды, корица, мед):
   - Аппетитное название десерта
   - Рецепт в 2 быстрых шага (смешать вилкой / запечь в микроволновке за 1 минуту)
   - ⚖️ Вес готовой порции: ~ХХХ г | КБЖУ порции: ~ХХХ ккал (Б: Х г, Ж: Х г, У: Х г)
   - Почему он снимет тягу (белок насыщает, хром/магний в какао гасят импульс).

3. 🩹 ЕСЛИ УЖЕ {gc['ate_verb'].upper()} МАГАЗИННУЮ ШОКОЛАДКУ ИЛИ ТОРТ (ПЛАН ДЕЙСТВИЙ):
   Конкретная, спокойная инструкция на сегодня:
   - Не пропускать следующие приемы пищи и ни в коем случае не голодать завтра!
   - Что добавить в следующий прием пищи (порция клетчатки: огурцы/зелень + нежирный белок), чтобы сгладить скачок сахара.
   - Как легко вписать это в дневник питания.

4. В самом конце добавь очень душевную мотивирующую фразу в курсиве ({'для мужчины: ты силен, держи ритм' if gc['gender_str'] == 'мужской' else 'для девушки: ты прекрасна, всё получится'}).
"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content


async def generate_family_split_meal(profile: Dict[str, Any], dish_idea: str = "") -> str:
    """Генерация концепции Семейный ужин — разные тарелки."""
    client = get_llm_client()
    system_prompt = build_nutritionist_system_prompt(profile)
    target_cals = profile.get("target_calories", 1800)

    user_prompt = f"""
Составь рецепт одного общего ужина для семьи, но с РАЗНЫМИ ТАРЕЛКАМИ (раздельными граммовками):
Пожелание по блюду: {dish_idea if dish_idea else "вкусный уютный домашний ужин из доступных продуктов"}.

СТРУКТУРА ОТВЕТА:
1. 🍲 Название общего блюда и простой пошаговый рецепт приготовления на сковороде/в духовке.
2. 👩 Тарелка для Неё (цель: дефицит калорий / форма, норма ~{target_cals} ккал/день):
   • Точный вес каждого компонента на весах в граммах (например: 120 г запеченной курицы, 80 г гарнира, 180 г салата)
   • КБЖУ порции: ~ХХХ ккал | Б: Х г | Ж: Х г | У: Х г
3. 👨 Тарелка для Него (сытная мужская порция на поддержание/силу):
   • Точный вес каждого компонента на весах в граммах (например: 220 г курицы, 200 г гарнира, 100 г салата + полезная заправка)
   • КБЖУ порции: ~ХХХ ккал | Б: Х г | Ж: Х г | У: Х г
4. 💡 Секрет шефа: как готовить в одной посуде, а варьировать только пропорцию белка/углеводов/клетчатки в тарелке.
5. Теплое семейное пожелание.
"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content


async def replace_single_meal(profile: Dict[str, Any], meal_type: str, current_dish: str = "") -> str:
    """Генерация альтернативного блюда взамен текущего в меню."""
    client = get_llm_client()
    gender = profile.get("gender", "женский")
    gc = get_gender_context(gender)
    system_prompt = build_nutritionist_system_prompt(profile)

    user_prompt = f"""
{gc['noun_nom'].capitalize()} хочет заменить блюдо в меню:
Прием пищи: {meal_type}
Текущее блюдо, которое не хочется / нет продуктов: {current_dish if current_dish else "стандартное блюдо"}

Предложи 2 отличных альтернативных варианта на замену:
- Примерно с таким же КБЖУ, чтобы не ломать суточный баланс {gc['noun_gen']}.
- Из простых доступных продуктов.
- С точным весом порции в граммах и КБЖУ.
- С кратким рецептом за 10-15 минут.
"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

