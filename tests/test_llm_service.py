"""AI-слой: промпты, гендерный контекст, парсеры ответов, моки вместо живого LLM."""

import asyncio
import json
from types import SimpleNamespace

import llm_service
from tests.test_database import PROFILE


def run(coro):
    return asyncio.run(coro)


# ------------------------- Фабрика мок-клиента LLM -------------------------

def _fake_client_response(text: str):
    """Собирает объект вида response.choices[0].message.content = text."""
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class FakeLLMClient:
    def __init__(self, text: str = "Ответ нейросети", error: Exception = None):
        self._text = text
        self._error = error
        self.calls = []

        class _Completions:
            def __init__(self, owner):
                self._owner = owner

            def create(self, **kwargs):
                self._owner.calls.append(kwargs)
                if self._owner._error is not None:
                    raise self._owner._error
                return _fake_client_response(self._owner._text)

        self.chat = SimpleNamespace(completions=_Completions(self))


def _patch_llm(monkeypatch, client):
    monkeypatch.setattr(llm_service, "get_llm_client", lambda: client)


# ------------------------- Гендерный контекст -------------------------

def test_gender_context_morphology():
    male = llm_service.get_gender_context("мужской")
    female = llm_service.get_gender_context("женский")
    assert male["noun_nom"] == "подопечный" and male["ate_verb"] == "съел"
    assert female["noun_nom"] == "подопечная" and female["ate_verb"] == "съела"
    assert "тестостерон" in male["accent"]
    assert "гормональный" in female["accent"]


def test_system_prompt_carries_profile_invariants():
    """AGENTS.md Правила 5-6: граммовки, любимые продукты, аллергии, стоп-лист."""
    prompt = llm_service.build_nutritionist_system_prompt(PROFILE)
    assert "Вес порции" in prompt and "КБЖУ" in prompt
    assert PROFILE["favorite_foods"] in prompt
    assert PROFILE["allergies"] in prompt
    assert PROFILE["disliked_foods"] in prompt
    assert "08:30" in prompt
    assert "ГОТОВИТЬ НА 2-3 ДНЯ ВПЕРЁД" in prompt


def test_system_prompt_male_morphology():
    male = {**PROFILE, "gender": "мужской"}
    prompt = llm_service.build_nutritionist_system_prompt(male)
    assert "ПОДОПЕЧНОГО" in prompt
    assert "ПОДОПЕЧНОЙ" not in prompt


# ------------------------- Парсер текстового расчета КБЖУ -------------------------

def test_extract_kbzhu_from_totals_block():
    text = ("📊 Расчет КБЖУ (Овсянка с ягодами):\n"
            "• Овсянка (50 г): ~190 ккал\n"
            "ИТОГО:\n"
            "• Калории: ~420 ккал\n"
            "• Белки: ~24,5 г\n"
            "• Жиры: ~14,2 г\n"
            "• Углеводы: ~48,1 г")
    data = llm_service.extract_kbzhu_from_calc_result(text)
    assert data["dish_name"] == "Овсянка с ягодами"
    assert data["calories"] == 420.0
    assert data["protein"] == 24.5
    assert data["fat"] == 14.2
    assert data["carbs"] == 48.1


def test_extract_kbzhu_empty_text_fallback():
    data = llm_service.extract_kbzhu_from_calc_result("", "Мой ужин")
    assert data["dish_name"] == "Мой ужин"
    assert data["calories"] == 0.0


# ------------------------- Парсер Vision-ответов -------------------------

def test_parse_vision_json_response():
    content = json.dumps({
        "is_food": True, "dish_name": "Овсяноблин", "weight_g": 210,
        "calories": 320.5, "protein": 18.0, "fat": 12.0, "carbs": 30.0,
        "components": [{"name": "овсянка", "weight_g": 40}],
        "comment": "Сбалансированный завтрак."
    })
    data = llm_service.parse_vision_response("```json\n" + content + "\n```")
    assert data["is_food"] is True
    assert data["dish_name"] == "Овсяноблин"
    assert data["calories"] == 320.5
    assert len(data["components"]) == 1


def test_parse_vision_template_response():
    content = ("• Блюдо: Гречка с курицей\n"
               "• Вес порции: ~350-400 г\n"
               "• КБЖУ: ~510 ккал | Б: 42 г | Ж: 11 г | У: 58 г\n"
               "• Состав: гречка 80 г, филе 130 г, салат 150 г\n"
               "• Польза: сложные углеводы и белок.")
    data = llm_service.parse_vision_response(content)
    assert data["is_food"] is True
    assert data["dish_name"] == "Гречка с курицей"
    assert data["weight_g"] == 375.0  # среднее диапазона 350-400
    assert data["calories"] == 510.0
    assert data["protein"] == 42.0


def test_parse_vision_non_food():
    data = llm_service.parse_vision_response("• НЕ ЕДА: на фото кот. Пришлите тарелку.")
    assert data["is_food"] is False
    assert "кот" in data["comment"]


def test_parse_vision_weight_only_calories_fallback():
    data = llm_service.parse_vision_response("• Блюдо: Суп\n• Вес порции: ~300 г")
    assert data["calories"] == 360.0  # 300 г * 1.2


# ------------------------- Живые вызовы через мок -------------------------

def test_generate_day_menu_uses_profile(monkeypatch):
    client = FakeLLMClient(text="Меню дня готово")
    _patch_llm(monkeypatch, client)
    result = run(llm_service.generate_day_menu(PROFILE, extra_wishes="побольше рыбы"))
    assert result == "Меню дня готово"
    assert len(client.calls) == 1
    sent = client.calls[0]
    assert sent["model"] == llm_service.LLM_MODEL
    user_prompt = sent["messages"][1]["content"]
    system_prompt = sent["messages"][0]["content"]
    assert "побольше рыбы" in user_prompt
    assert PROFILE["favorite_foods"] in system_prompt


def test_analyze_food_photo_unsupported_model_message(monkeypatch):
    """Провайдер без Vision: внятное сообщение вместо 'снимок не разобран'."""
    error = RuntimeError("400 Invalid parameter: messages with image_url content are not supported")
    _patch_llm(monkeypatch, FakeLLMClient(error=error))
    result = run(llm_service.analyze_food_photo(b"\x89PNG...", PROFILE))
    assert result["is_food"] is False
    assert "не умеет анализировать" in result["comment"]


def test_analyze_food_photo_generic_error_stays_friendly(monkeypatch):
    _patch_llm(monkeypatch, FakeLLMClient(error=RuntimeError("connection reset")))
    result = run(llm_service.analyze_food_photo(b"\x89PNG...", PROFILE))
    assert result["is_food"] is False
    assert "Не удалось разобрать снимок" in result["comment"]


def test_analyze_food_photo_happy_path(monkeypatch):
    vision_answer = ("• Блюдо: Творог с ягодами\n"
                     "• Вес порции: ~200 г\n"
                     "• КБЖУ: ~180 ккал | Б: 24 г | Ж: 2 г | У: 12 г\n"
                     "• Польза: белковый перекус.")
    _patch_llm(monkeypatch, FakeLLMClient(text=vision_answer))
    result = run(llm_service.analyze_food_photo(b"\x89PNG...", PROFILE))
    assert result["is_food"] is True
    assert result["dish_name"] == "Творог с ягодами"
    assert result["calories"] == 180.0
    assert result["protein"] == 24.0
