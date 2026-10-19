# 🥑 Пищеблок — техническая документация

> Эта версия README — для опытных пользователей и разработчиков. Короткий вариант
> для быстрого старта — [README.md](README.md). Пошаговый гайд без консоли —
> [ИНСТРУКЦИЯ_ПОЛЬЗОВАТЕЛЯ.md](ИНСТРУКЦИЯ_ПОЛЬЗОВАТЕЛЯ.md).

Telegram-бот: персональный нутрициолог и семейный шеф-повар. Единый процесс
polling, SQLite рядом с кодом, LLM через OpenAI-совместимый API, локальный Whisper.

## Стек

| Компонент | Выбор | Комментарий |
|---|---|---|
| Python | 3.10 – 3.12 | 3.13 не гарантируется: колёса `ctranslate2` |
| Bot framework | Aiogram 3.22 | FSM, Routers, MemoryStorage, long polling |
| БД | SQLite + aiosqlite | один файл `nutrition_chef.db`, 5 таблиц |
| LLM | DeepSeek (по умолчанию) / Gemini / любой OpenAI-совместимый шлюз | текстовые задачи + Vision, если модель мультимодальная |
| ASR | faster-whisper (tiny, CPU int8) | локально, аудио не покидает машину |
| Конфиг | python-dotenv | `.env` (+ `validate_config()` preflight) |
| Тесты | pytest | 47 тестов, моки LLM, отдельная тестовая БД |

## Архитектура

Слои строго вниз, без обратных зависимостей:

```
handlers/  (Aiogram Routers: Telegram I/O, FSM, клавиатуры)
    │
    ├── llm_service.py   (единственный клиент LLM: промпты, генерация, парсеры ответов)
    ├── nutrition.py     (Миффлин-Сан Жеор, цели, прогресс-бары — чистая математика)
    ├── database.py      (aiosqlite: users, daily_food_logs, weight_history,
    │                     favorites, chat_messages)
    └── keyboards.py / states.py / config.py
```

- `handlers/` не считают БЖУ и не ходят в сеть напрямую — только через `llm_service`.
- `nutrition.py` и `llm_service.py` не знают про Telegram — поэтому покрываются юнит-тестами без бота.
- Инварианты проекта (граммовки, стоп-листы, ноль тихих сбоев и др.) зафиксированы в **[AGENTS.md](AGENTS.md)** — перед доработками прочитать обязательно.

```
Пищеблок/
├── main.py                   # точка входа: preflight, команды, роутеры, polling
├── config.py                 # .env + validate_config() с человеческими ошибками
├── database.py / nutrition.py / llm_service.py / keyboards.py / states.py
├── handlers/                 # 9 роутеров по доменам
├── tests/                    # pytest: conftest подменяет DB_PATH и ключи
├── test_bot_core.py          # интеграционный прогон (10 сьютов)
├── test_local_dataset.py     # оффлайн-проверки фикстур и Whisper
├── test_data/                # аудио, фото, JSON-сценарии
├── ЗАПУСК_БОТА.cmd           # Windows-лаунчер: venv, deps, preflight, запуск
├── scripts/unix/run.sh       # Linux/macOS-лаунчер
├── .github/workflows/ci.yml  # CI: pytest + main.py --check, ubuntu/windows
├── .env.example              # шаблон настроек (.env не коммитится)
└── .gitignore / .gitattributes / AGENTS.md / LICENSE / README* / ИНСТРУКЦИЯ*
```

## Все переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | токен от @BotFather (обязателен) |
| `LLM_PROVIDER` | `deepseek` | `deepseek` или `gemini` |
| `DEEPSEEK_API_KEY` | — | ключ DeepSeek (или шлюза) |
| `LLM_MODEL` | `deepseek-flash` | модель; для фото нужна мультимодальная |
| `LLM_BASE_URL` | `https://api.deepseek.com` | любой OpenAI-совместимый эндпоинт |
| `LLM_TIMEOUT` | `120` | таймаут LLM, сек (reasoning-модели медленные) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | — / `gemini-2.5-flash` | вариант `LLM_PROVIDER=gemini` |
| `WHISPER_MODEL` | `tiny` | `tiny` / `base` / `small` — точность vs скорость |
| `PROXY_URL` | — | прокси, если Telegram/API недоступны напрямую |
| `DB_PATH` | `nutrition_chef.db` | путь к SQLite (тесты переопределяют) |

Ключи с префиксом `sk-sk-` автоматически чинятся до `sk-` (историческая опечатка).

## Провайдеры и Vision

- **DeepSeek**: текст — `deepseek-chat` / `deepseek-reasoner`. Разбор фото требует
  мультимодальную модель: если провайдер/модель Vision не поддерживает, бот не
  падает — возвращает понятное сообщение, текстовые функции работают.
- **Gemini**: `LLM_PROVIDER=gemini` + `GEMINI_API_KEY` (OpenAI-совместимый эндпоинт Gemini).
- **Свой шлюз** (OpenRouter, vLLM и т.п.): укажите `LLM_BASE_URL` + `LLM_MODEL` + ключ в `DEEPSEEK_API_KEY`.

## Установка и запуск вручную

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip.exe
cp .env.example .env                             # Windows: copy .env.example .env
.venv/bin/python main.py                         # Windows: .venv\Scripts\python.exe main.py
```

Preflight без запуска бота (валидация токена, ключей, прав на запись БД):

```bash
python main.py --check    # «OK: конфигурация в порядке» или список проблем по-русски
```

## Тесты и CI

```bash
python -m pytest tests -q      # 47 тестов: формулы, БД, промпты, парсеры, клавиатуры
python test_bot_core.py        # интеграционный набор (10 сьютов, тестовая БД)
python test_local_dataset.py   # оффлайн: дата-сет, фикстуры LLM, локальный Whisper
```

- `tests/conftest.py` до импортов выставляет ключи-заглушки и `DB_PATH` в `tests/` —
  сьют герметичен: 0 сети, 0 токенов, боевая БД не трогается.
- CI (`.github/workflows/ci.yml`): матрица ubuntu/windows, pytest + смоук `--check`
  на заглушках при каждом пуше.

## Эксплуатация и ограничения

- **Однопроцессовый polling.** FSM в `MemoryStorage`, интерактивные списки покупок —
  в памяти процесса: рестарт сбрасывает незавершённую анкету и чек-боксы. Для
  семейного масштаба — осознанный выбор; под мультиинстанс нужны Redis-хранилище.
- **Куда уходят данные:** голос — никуда (локальный Whisper); фото блюд — в API
  вашего LLM-провайдера; `.env` и БД исключены из git (`.gitignore`).
- **Autostart:** Windows — Планировщик заданий на `ЗАПУСК_БОТА.cmd`; Linux — systemd
  юнит с `Restart=always` на `scripts/unix/run.sh`.
- БД мигрирует автоматически при старте (`init_db`, аддитивные ALTER).

## Разработка

Перед доработками — **[AGENTS.md](AGENTS.md)**: 10 инвариантов (граммовки для весов,
стоп-листы, запрет `except: pass`, CRLF для `.cmd` и др.) и регламент проверки:
`import main` → `--check` → офлайн-тесты → `pytest` → интеграционный набор.

Лицензия: **[MIT](LICENSE)**. Рекомендации бота не заменяют консультацию врача.
