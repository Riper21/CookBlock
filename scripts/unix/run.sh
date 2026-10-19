#!/usr/bin/env bash
# Пищеблок: запуск бота на Linux / macOS.
# Первый запуск создает окружение .venv и ставит зависимости.
set -euo pipefail
cd "$(dirname "$0")/.."

# ---------- 1. Файл настроек .env ----------
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[!] Создан файл .env из шаблона .env.example."
    echo "    Впишите в него TELEGRAM_BOT_TOKEN и ключ нейросети, затем запустите снова."
    exit 1
fi

# ---------- 2. Python ----------
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo "[ОШИБКА] Python 3.10+ не найден. Установите: apt install python3 python3-venv (Debian/Ubuntu)."
    exit 1
fi

# ---------- 3. Виртуальное окружение и зависимости ----------
if [ ! -x .venv/bin/python ]; then
    echo "[*] Создаю виртуальное окружение .venv ..."
    "$PYTHON_BIN" -m venv .venv
fi
if [ ! -f .venv/.deps_ok ]; then
    echo "[*] Устанавливаю зависимости ..."
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
    touch .venv/.deps_ok
fi

# ---------- 4. Проверка настроек и запуск ----------
echo "[*] Проверяю настройки .env ..."
.venv/bin/python main.py --check

echo "[*] Запускаю бота. Остановка - Ctrl+C."
exec .venv/bin/python main.py
