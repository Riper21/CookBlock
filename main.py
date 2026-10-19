"""
Главная точка входа для запуска бота «Пищеблок» (Диетолог-Нутрициолог и Семейный шеф-повар).

Запуск:            py main.py
Только проверка
конфигурации:      py main.py --check
"""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import config
import database
from config import validate_config
from handlers import (
    common,
    profile,
    menu_planner,
    fridge_chef,
    kbzhu_calc,
    food_diary,
    favorites,
    vision_voice,
    sos_sweet
)

# Настройка кодировки вывода для Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("FoodChefBot")


def run_preflight() -> bool:
    """Предполётная проверка настроек: внятные сообщения вместо трейсбеков."""
    problems = validate_config()
    if problems:
        print("=" * 64)
        print("  БОТ НЕ ЗАПУЩЕН - не хватает настроек в файле .env")
        print("=" * 64)
        for i, problem in enumerate(problems, start=1):
            print(f"\n  Проблема {i}: {problem}")
        print("\n  Что делать:")
        print("  1. Откройте файл .env в папке проекта (рядом с main.py).")
        print("     Если его нет - скопируйте .env.example и переименуйте в .env.")
        print("  2. Впишите TELEGRAM_BOT_TOKEN и ключ нейросети.")
        print("  3. Пошаговая инструкция: ИНСТРУКЦИЯ_ПОЛЬЗОВАТЕЛЯ.md, раздел «Настройка».")
        print("=" * 64)
        return False
    return True


async def main():
    logger.info("Инициализация базы данных...")
    await database.init_db()

    logger.info("Запуск Telegram бота...")
    session = None
    if config.PROXY_URL and config.PROXY_URL.strip():
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=config.PROXY_URL.strip())

    try:
        bot = Bot(
            token=config.TELEGRAM_BOT_TOKEN,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
    except Exception as e:
        logger.error(f"Не удалось создать бота - неверный TELEGRAM_BOT_TOKEN: {e}")
        print("=" * 64)
        print("  TELEGRAM_BOT_TOKEN отклонен Telegram. Скорее всего токен скопирован")
        print("  не полностью или отозван. Получите новый в @BotFather (/mybots).")
        print("=" * 64)
        return

    # Регистрация системного меню команд Telegram (синяя кнопка "Меню" внизу слева)
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="diary", description="📖 Дневник питания за сегодня"),
        BotCommand(command="daymenu", description="☀️ Меню на день с рецептами"),
        BotCommand(command="menu", description="📅 Меню на неделю + покупки"),
        BotCommand(command="family", description="👨‍👩‍👧 Семейный ужин — разные тарелки"),
        BotCommand(command="photo", description="📸 Оценить блюдо по фото (Vision)"),
        BotCommand(command="voice", description="🎙️ Надиктовать еду голосом (Whisper)"),
        BotCommand(command="fridge", description="🍳 Что приготовить из холодильника"),
        BotCommand(command="kbzhu", description="📊 Рассчитать КБЖУ блюда"),
        BotCommand(command="sos", description="🍫 SOS: Тянет на сладкое / Срыв"),
        BotCommand(command="favorites", description="⭐ Моё избранное"),
        BotCommand(command="profile", description="👤 Мой профиль и норма КБЖУ"),
        BotCommand(command="reset", description="🔄 Сброс контекста диалога"),
        BotCommand(command="start", description="🚀 Главное меню")
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning(f"Не удалось обновить системное меню команд Telegram (временный сбой сети): {e}")

    dp = Dispatcher()

    # Регистрация роутеров в правильном порядке
    # (специализированные первыми, общий диалог последним)
    dp.include_router(profile.router)
    dp.include_router(food_diary.router)
    dp.include_router(menu_planner.router)
    dp.include_router(fridge_chef.router)
    dp.include_router(kbzhu_calc.router)
    dp.include_router(vision_voice.router)
    dp.include_router(sos_sweet.router)
    dp.include_router(favorites.router)
    dp.include_router(common.router)

    logger.info("🤖 Бот-нутрициолог и шеф-повар успешно запущен и готов к работе!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    if "--check" in sys.argv:
        # Режим проверки настроек без запуска бота (для диагностики и CI)
        if run_preflight():
            print("OK: конфигурация в порядке, бот готов к запуску.")
        else:
            sys.exit(1)
    else:
        if not run_preflight():
            sys.exit(1)
        try:
            asyncio.run(main())
        except (KeyboardInterrupt, SystemExit):
            logger.info("Бот остановлен.")
