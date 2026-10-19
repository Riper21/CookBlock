@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
title Персональный Бот-Нутрициолог «Пищеблок»

echo =====================================================================
echo    ЗАПУСК БОТА-НУТРИЦИОЛОГА И ШЕФ-ПОВАРА ПИЩЕБЛОК
echo =====================================================================
echo.

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" > nul
        echo [!] Создан файл .env из шаблона .env.example.
        echo Пожалуйста, откройте .env в Блокноте и укажите токены.
        pause
        exit /b 1
    )
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python
    ) else (
        echo [ОШИБКА] Python не найден на вашем компьютере!
        echo Пожалуйста, установите Python с сайта https://www.python.org/
        pause
        exit /b 1
    )
)

echo [*] Запуск бота через %PYTHON_CMD% main.py...
echo [*] Для остановки закройте это окно или нажмите Ctrl+C.
echo.

%PYTHON_CMD% main.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Бот завершил работу с ошибкой (код: %errorlevel%).
    pause
)
