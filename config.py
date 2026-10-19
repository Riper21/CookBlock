"""
Модуль конфигурации бота-нутрициолога и шеф-повара.
Поддерживает DeepSeek (по умолчанию, OpenAI-совместимый API) и Google Gemini.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных из .env, если он существует
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# Токен бота Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "ВАШ_ТЕЛЕГРАМ_ТОКЕН_ОТ_BotFather")

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
PROXY_URL = os.getenv("PROXY_URL", "")

# Путь к файлу базы данных SQLite
DB_PATH = BASE_DIR / "nutrition_chef.db"
