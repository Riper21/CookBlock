"""
Обработчик мультимодальных сообщений:
1. Фотографий еды через DeepSeek Flash Vision (F.photo).
2. Голосовых сообщений через автономный Whisper (F.voice).
Обеспечивает мгновенный расчет КБЖУ и занесение в Дневник питания в 1 клик.
"""

import io
import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from database import get_user_profile, add_food_log
from keyboards import get_main_keyboard, get_cancel_keyboard, get_vision_log_keyboard
import llm_service

logger = logging.getLogger(__name__)
router = Router()

# Кэш последнего распознанного по фото/голосу блюда для каждого пользователя
LAST_VISION_MEALS: dict = {}


# ==================== КНОПКИ ВЫЗОВА И ПОЯСНЯЮЩИЕ ИНСТРУКЦИИ ====================

@router.message(F.text == "📸 Фото тарелки (Vision)")
@router.message(Command("photo"))
async def prompt_food_photo(message: types.Message):
    """Инструкция и приглашение отправить фото тарелки для Vision-анализа."""
    await message.answer(
        "📸 **Оценка блюда по фото (DeepSeek Flash Vision)** 🥑✨\n\n"
        "Сфотографируйте вашу тарелку, десерт, перекус или упаковку продукта и отправьте сюда!\n\n"
        "🤖 **Что сделает нейросеть:**\n"
        "• Распознает все компоненты на вашей тарелке.\n"
        "• Оценит размер порции в граммах для кухонных весов.\n"
        "• Рассчитает калории, белки, жиры и углеводы (КБЖУ).\n"
        "• Предложит кнопки быстрой записи в **Дневник питания** (`🍳 В Завтрак`, `🥗 В Обед` и т.д.).\n\n"
        "👉 _Прикрепите фото через скрепку 📎 или сделайте снимок на камеру 📷 и отправьте в чат:_",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == "🎙️ Голосовой ввод (Whisper)")
@router.message(Command("voice"))
async def prompt_voice_message(message: types.Message):
    """Инструкция и приглашение надиктовать еду голосом для Whisper."""
    await message.answer(
        "🎙️ **Голосовой дневник питания (Локальный Whisper)** 🥑✨\n\n"
        "Вам не нужно вбивать ингредиенты руками! Просто зажмите микрофон и надиктуйте, что вы съели.\n\n"
        "💡 **Примеры фраз:**\n"
        "• _«На завтрак съел 2 вареных яйца, тост из зернового хлеба с авокадо и выпил кофе»_\n"
        "• _«Обед: 150 грамм запеченной индейки, 80 грамм гречки и салат из огурцов»_\n"
        "• _«Перекусил горстью миндаля и половинкой яблока»_\n\n"
        "🤖 **Что сделает бот:**\n"
        "• Локальная модель Whisper автономно расшифрует русскую речь на CPU (без передачи аудио в облако).\n"
        "• Диетолог рассчитает КБЖУ и пользу каждого продукта.\n"
        "• Вы сможете в 1 клик занести блюдо в **Дневник питания**!\n\n"
        "👉 _Зажмите значок микрофона 🎙️ справа внизу и надиктуйте ваш прием пищи:_",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )


# ==================== ОБРАБОТКА МУЛЬТИМОДАЛЬНЫХ СООБЩЕНИЙ ====================

@router.message(F.photo)
async def handle_food_photo(message: types.Message):
    """
    Обработка входящего фото тарелки с едой через DeepSeek Flash Vision.
    Скачивает изображение в наилучшем качестве, отправляет в LLM
    и выводит карточку КБЖУ с кнопками записи в дневник.
    """
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    if not profile:
        profile = {}

    status_msg = await message.answer(
        "🔎 Анализирую ваше блюдо через **DeepSeek Flash Vision**...\n"
        "Определяю ингредиенты, вес порции и рассчитываю КБЖУ 🥑",
        parse_mode="Markdown"
    )
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Получаем фото наибольшего разрешения
        photo = message.photo[-1]
        file_io = io.BytesIO()
        await message.bot.download(photo, destination=file_io)
        image_bytes = file_io.getvalue()

        # Вызов мультимодального анализа
        result = await llm_service.analyze_food_photo(image_bytes, profile)
        await status_msg.delete()

        if not result.get("is_food", True):
            comment = result.get("comment", "На фото не обнаружено готовое блюдо.")
            non_food_text = (
                f"ℹ️ **Анализ фото:**\n\n"
                f"{comment}\n\n"
                f"📸 Чтобы рассчитать калории, пожалуйста, сфотографируйте вашу тарелку с едой или продукты."
            )
            try:
                await message.answer(
                    non_food_text,
                    reply_markup=get_main_keyboard(),
                    parse_mode="Markdown"
                )
            except TelegramBadRequest:
                await message.answer(
                    non_food_text,
                    reply_markup=get_main_keyboard(),
                    parse_mode=None
                )
            return

        # Сохраняем в кэш для быстрой записи по кнопкам
        LAST_VISION_MEALS[user_id] = result

        dish_name = result.get("dish_name", "Блюдо по фото")
        weight_g = result.get("weight_g", 0.0)
        calories = result.get("calories", 0.0)
        protein = result.get("protein", 0.0)
        fat = result.get("fat", 0.0)
        carbs = result.get("carbs", 0.0)
        components = result.get("components", [])
        comment = result.get("comment", "")

        comp_lines = []
        for c in components:
            if isinstance(c, dict):
                c_name = c.get("name", "")
                c_w = c.get("weight_g", 0.0)
                c_cal = c.get("calories", 0.0)
                if c_name:
                    if c_w > 0 and c_cal > 0:
                        comp_lines.append(f"• {c_name} (~{c_w:.0f}г — ~{c_cal:.0f} ккал)")
                    else:
                        comp_lines.append(f"• {c_name}")
            elif isinstance(c, str) and c.strip():
                comp_lines.append(f"• {c.strip()}")

        comp_text = "\n".join(comp_lines) if comp_lines else "• Состав определен комплексно"

        card_text = (
            f"📸 **Распознано:** _{dish_name}_\n"
            f"⚖️ **Примерный вес порции:** ~{weight_g:.0f} г\n\n"
            f"📊 **КБЖУ порции на тарелке:**\n"
            f"🔥 **Калории:** ~{calories:.0f} ккал\n"
            f"🥩 **Белки:** {protein:.1f} г\n"
            f"🥑 **Жиры:** {fat:.1f} г\n"
            f"🍞 **Углеводы:** {carbs:.1f} г\n\n"
            f"🥗 **Состав тарелки:**\n"
            f"{comp_text}\n\n"
            f"💡 **Комментарий нутрициолога:**\n"
            f"_{comment}_\n\n"
            f"👉 _Куда записать этот прием пищи в ваш Дневник питания?_"
        )

        try:
            await message.answer(
                card_text,
                reply_markup=get_vision_log_keyboard(),
                parse_mode="Markdown"
            )
        except TelegramBadRequest:
            await message.answer(
                card_text,
                reply_markup=get_vision_log_keyboard(),
                parse_mode=None
            )

    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}", exc_info=True)
        await status_msg.delete()
        await message.answer(
            f"⚠️ Не удалось обработать фото: {e}\n"
            "Попробуйте отправить снимок еще раз.",
            reply_markup=get_main_keyboard()
        )


@router.callback_query(F.data.startswith("vlog_"))
async def process_vision_log_callback(callback: types.CallbackQuery):
    """Быстрая запись распознанного по фото блюда в выбранный прием пищи."""
    action = callback.data.replace("vlog_", "")

    if action == "cancel":
        await callback.answer("Запись отменена.")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer("👌 Запись отменена. Данные не внесены в дневник.", reply_markup=get_main_keyboard())
        return

    meal_type = action
    user_id = callback.from_user.id
    meal_data = LAST_VISION_MEALS.get(user_id)

    if not meal_data:
        await callback.answer("Данные фото устарели. Пожалуйста, отправьте фото снова.", show_alert=True)
        return

    await add_food_log(
        user_id=user_id,
        meal_type=meal_type,
        food_description=meal_data["dish_name"],
        calories=meal_data["calories"],
        protein=meal_data["protein"],
        fat=meal_data["fat"],
        carbs=meal_data["carbs"]
    )

    await callback.answer(f"Записано в {meal_type}!")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        f"✅ **{meal_type} успешно добавлен по фото в Дневник питания!**\n\n"
        f"🍽️ _{meal_data['dish_name']}_\n"
        f"🔥 +{meal_data['calories']:.0f} ккал | "
        f"Б: {meal_data['protein']:.1f}г | "
        f"Ж: {meal_data['fat']:.1f}г | "
        f"У: {meal_data['carbs']:.1f}г\n\n"
        "Чтобы посмотреть общую сумму за день, нажмите кнопку **📖 Дневник питания 🥑** ниже 👇",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.voice)
async def handle_voice_message(message: types.Message):
    """
    Обработка голосовых сообщений через локальный автономный Whisper.
    """
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    if not profile:
        profile = {}

    status_msg = await message.answer(
        "🎙️ Слушаю голосовое сообщение...",
        parse_mode="Markdown"
    )
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Проверяем наличие установленного whisper
        try:
            from faster_whisper import WhisperModel
            import tempfile
            import os

            voice = message.voice
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_f:
                tmp_path = tmp_f.name

            await message.bot.download(voice, destination=tmp_path)

            # Локальная модель tiny (быстрая и компактная)
            whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = whisper_model.transcribe(tmp_path, language="ru")
            recognized_text = " ".join([seg.text for seg in segments]).strip()

            try:
                os.remove(tmp_path)
            except Exception:
                pass

            if not recognized_text:
                await status_msg.delete()
                await message.answer("⚠️ Не удалось разобрать речь. Попробуйте наговорить четче или напишите текстом.")
                return

            await status_msg.edit_text(f"🗣️ _«{recognized_text}»_\n\n⚖️ Считаю КБЖУ...")

            # Рассчитываем КБЖУ через DeepSeek Flash
            calc_result = await llm_service.calculate_dish_kbzhu(profile, recognized_text)
            parsed_data = llm_service.extract_kbzhu_from_calc_result(calc_result, fallback_dish_name=recognized_text[:30])
            if parsed_data.get("calories", 0.0) <= 0:
                parsed_data = await llm_service.parse_meal_kbzhu(recognized_text, profile)

            from handlers.kbzhu_calc import LAST_CALCULATED_MEALS
            from keyboards import get_meal_type_log_keyboard
            LAST_CALCULATED_MEALS[user_id] = parsed_data

            await status_msg.delete()

            chunks = [calc_result[i:i + 4000] for i in range(0, len(calc_result), 4000)]
            for i, chunk in enumerate(chunks):
                kb = get_meal_type_log_keyboard() if i == len(chunks) - 1 else None
                try:
                    await message.answer(chunk, reply_markup=kb, parse_mode="Markdown")
                except Exception:
                    await message.answer(chunk, reply_markup=kb, parse_mode=None)

        except ImportError:
            await status_msg.delete()
            await message.answer(
                "🎙️ Модуль распознавания речи настраивается на вашем сервере.\n"
                "Пока вы можете отправить состав текстом (кнопка **📊 Рассчитать КБЖУ**) или отправить **фото тарелки 📸**!",
                reply_markup=get_main_keyboard()
            )

    except Exception as e:
        logger.error(f"Ошибка обработки аудио: {e}", exc_info=True)
        await status_msg.delete()
        await message.answer(
            f"⚠️ Не удалось обработать аудио: {e}\n"
            "Пожалуйста, напишите состав блюда текстом или отправьте фото тарелки.",
            reply_markup=get_main_keyboard()
        )
