"""
Обработчик экстренной помощи при тяге к сладкому или срыве («SOS: Сладкое»).
Помогает справиться с импульсом без чувства вины, предлагает 3 экспресс-десерта
за 2-3 минуты и дает четкий план компенсации дня.
"""

from aiogram import Router, F, types
from aiogram.filters import Command
from database import get_user_profile
from keyboards import get_main_keyboard
import llm_service

router = Router()


@router.message(F.text == "🍫 SOS: Сладкое / Срыв")
@router.message(F.text == "🍫 SOS: Сладкое")
@router.message(Command("sos"))
async def handle_sweet_sos(message: types.Message):
    """Генерация помощи нутрициолога при тяге к сладкому."""
    user_id = message.from_user.id
    profile = await get_user_profile(user_id)
    if not profile:
        profile = {}

    status_msg = await message.answer(
        "🍫 Подбираю экспресс-десерты за 2 минуты и рекомендации нутрициолога...",
        reply_markup=get_main_keyboard()
    )
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        advice = await llm_service.generate_sweet_sos(profile)
        await status_msg.delete()

        chunks = [advice[i:i + 4000] for i in range(0, len(advice), 4000)]
        for chunk in chunks:
            try:
                await message.answer(chunk, parse_mode="Markdown")
            except Exception:
                await message.answer(chunk, parse_mode=None)

    except Exception as e:
        await status_msg.delete()
        await message.answer(
            f"⚠️ Не удалось получить рекомендацию: {e}\n"
            "Попробуйте нажать кнопку еще раз чуть позже.",
            reply_markup=get_main_keyboard(),
            parse_mode=None
        )
