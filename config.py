"""
Модуль конфигурации бота-нутрициолога и шеф-повара.
Поддерживает DeepSeek (по умолчанию, OpenAI-совместимый API) и Google Gemini.
Все настройки читаются из файла .env рядом с main.py (шаблон: .env.example).
"""

import os
import re
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Загрузка переменных из .env, если он существует
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# Токен бота Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Провайдер нейросети: 'deepseek' (рекомендуется) или 'gemini'
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek").lower().strip()

# Ключ API: ищем DEEPSEEK_API_KEY, затем LLM_API_KEY, затем GEMINI_API_KEY
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
if DEEPSEEK_API_KEY.startswith("sk-sk-"):
    DEEPSEEK_API_KEY = DEEPSEEK_API_KEY[3:]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if LLM_PROVIDER == "gemini":
    LLM_API_KEY = GEMINI_API_KEY or os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
else:
    # По умолчанию DeepSeek
    LLM_API_KEY = DEEPSEEK_API_KEY or os.getenv("LLM_API_KEY", "") or GEMINI_API_KEY
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    LLM_MODEL = os.getenv("LLM_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-flash"))

# Опциональный прокси (например, "http://127.0.0.1:10809")
PROXY_URL = os.getenv("PROXY_URL", "").strip()

# Таймаут вызовов LLM в секундах: reasoning-модели (deepseek-flash и др.)
# думают небыстро, 60 секунд может не хватить
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

# Локальный Whisper (голосовой ввод): tiny/base/small
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny").strip() or "tiny"

# Путь к файлу базы данных SQLite (переопределяется в тестах и Docker)
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "nutrition_chef.db")))


def _looks_like_placeholder(value: str) -> bool:
    """Плейсхолдеры из .env.example или пустые значения - не настоящие ключи."""
    if not value:
        return True
    placeholders = ("ВАШ", "BOTFATHER", "ВАШ_КЛЮЧ", "ВАШ_ENDPOINT")
    return any(p in value.upper() for p in placeholders)


def validate_config() -> List[str]:
    """
    Предполётная проверка конфигурации (запускается до старта бота).
    Возвращает список проблем на русском языке. Пустой список = всё готово.
    """
    problems = []

    if not TELEGRAM_BOT_TOKEN:
        problems.append(
            "Не задан TELEGRAM_BOT_TOKEN - токен бота из @BotFather.\n"
            "       Получение: Telegram -> @BotFather -> /newbot -> скопировать токен."
        )
    elif _looks_like_placeholder(TELEGRAM_BOT_TOKEN):
        problems.append(
            "TELEGRAM_BOT_TOKEN всё ещё содержит заглушку из .env.example.\n"
            "       Вставьте настоящий токен вида 1234567890:AA..."
        )
    elif not re.match(r"^\d{6,}:[A-Za-z0-9_-]{30,}$", TELEGRAM_BOT_TOKEN):
        problems.append(
            "TELEGRAM_BOT_TOKEN выглядит некорректно (ожидается формат 1234567890:AA...).\n"
            "       Перекопируйте токен из @BotFather без пробелов и кавычек."
        )

    if LLM_PROVIDER == "gemini":
        key = GEMINI_API_KEY or os.getenv("LLM_API_KEY", "")
        if _looks_like_placeholder(key):
            problems.append(
                "LLM_PROVIDER=gemini, но GEMINI_API_KEY не задан или содержит заглушку.\n"
                "       Получение: https://aistudio.google.com/apikey"
            )
    else:
        key = LLM_API_KEY
        if _looks_like_placeholder(key):
            problems.append(
                "Не задан ключ нейросети (DEEPSEEK_API_KEY при LLM_PROVIDER=deepseek).\n"
                "       Получение: https://platform.deepseek.com/ -> API Keys."
            )

    if LLM_PROVIDER not in ("deepseek", "gemini"):
        problems.append(
            f"LLM_PROVIDER={LLM_PROVIDER!r} не поддерживается (ожидалось deepseek или gemini)."
        )

    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        problems.append(f"Не удалось создать папку для базы данных {DB_PATH.parent}: {e}")

    return problems
