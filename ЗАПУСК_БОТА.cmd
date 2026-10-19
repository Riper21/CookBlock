@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Пищеблок - персональный бот-нутрициолог

echo =====================================================================
echo    ПИЩЕБЛОК - бот-нутрициолог и семейный шеф-повар
echo    Первый запуск: создаем окружение и ставим зависимости.
echo =====================================================================
echo.

rem ---------- 1. Файл настроек .env ----------
if not exist ".env" (
    copy ".env.example" ".env" > nul
    echo [!] Создан файл .env из шаблона .env.example
    echo     Сейчас откроется Блокнот - впишите TELEGRAM_BOT_TOKEN
    echo     и ключ нейросети, сохраните файл и закройте Блокнот.
    echo.
    start "" notepad ".env"
    pause
)

rem ---------- 2. Поиск Python ----------
set "PYTHON_CMD="
py -3 --version > nul 2> nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    python --version > nul 2> nul && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo [ОШИБКА] Python не найден на этом компьютере!
    echo.
    echo Установите Python 3.10 - 3.12 с сайта https://www.python.org/downloads/
    echo ВАЖНО: при установке отметьте галочку "Add Python to PATH".
    echo После установки запустите этот файл заново.
    echo.
    pause
    exit /b 1
)

rem ---------- 3. Виртуальное окружение ----------
if not exist ".venv\Scripts\python.exe" (
    echo [*] Создаю виртуальное окружение .venv ...
    %PYTHON_CMD% -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo [ОШИБКА] Не удалось создать виртуальное окружение.
        echo         Подробности - ИНСТРУКЦИЯ_ПОЛЬЗОВАТЕЛЯ.md, раздел "Диагностика".
        pause
        exit /b 1
    )
)
set "VPY=%~dp0.venv\Scripts\python.exe"

rem ---------- 4. Зависимости (однократно) ----------
if not exist ".venv\.deps_ok" (
    echo [*] Устанавливаю зависимости: aiogram, openai, aiosqlite, whisper...
    echo     Это может занять несколько минут - не закрывайте окно.
    "%VPY%" -m pip install --upgrade pip
    "%VPY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ОШИБКА] Не удалось установить зависимости - проверьте интернет.
        echo         Повторите запуск позже или установите вручную командой:
        echo         .venv\Scripts\pip.exe install -r requirements.txt
        pause
        exit /b 1
    )
    type nul > ".venv\.deps_ok"
    echo [*] Зависимости установлены.
)

rem ---------- 5. Проверка настроек ----------
echo [*] Проверяю настройки .env ...
"%VPY%" main.py --check
if errorlevel 1 (
    echo.
    echo [!] Исправьте .env по подсказкам выше и запустите этот файл заново.
    pause
    exit /b 1
)

rem ---------- 6. Запуск ----------
echo [*] Запускаю бота. Остановка - крестик или Ctrl+C.
echo.
"%VPY%" main.py
if errorlevel 1 (
    echo.
    echo [!] Бот завершил работу с ошибкой (код: %errorlevel%).
    echo     Причины и решения - ИНСТРУКЦИЯ_ПОЛЬЗОВАТЕЛЯ.md, раздел "Диагностика".
    pause
)
