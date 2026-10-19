"""
Обработчик системы «Избранное» (сохранение, просмотр и удаление рецептов/меню/КБЖУ).
"""

import urllib.parse
from aiogram import Router, F, types
from aiogram.filters import Command
from database import (
    add_favorite,
    get_favorites,
    get_favorite_by_id,
    delete_favorite
)
from keyboards import (
    get_favorites_list_keyboard,
    get_favorite_item_keyboard,
    get_main_keyboard
)
from handlers.menu_planner import CURRENT_SHOPPING_LISTS, format_shopping_share_text

router = Router()


@router.callback_query(F.data.startswith("save_fav_"))
async def save_to_favorites_handler(callback: types.CallbackQuery):
    """Сохранение текущего ответа в Избранное."""
    category = callback.data.replace("save_fav_", "")
    user_id = callback.from_user.id
    message_text = callback.message.text or callback.message.caption or ""

    if not message_text and category != "shopping":
        await callback.answer("⚠️ Не удалось сохранить пустое сообщение.", show_alert=True)
        return

    # Если сохраняется список покупок, извлекаем полный список продуктов
    if category == "shopping" or "список покупок" in message_text.lower():
        category = "shopping"
        items = CURRENT_SHOPPING_LISTS.get(user_id, [])
        if items:
            message_text = format_shopping_share_text(items)
        elif not message_text:
            message_text = "🛒 Список покупок пуст."
        clean_title = "🛒 Список покупок"
    else:
        # Формируем заголовок из первой непустой строки сообщения
        lines = [line.strip() for line in message_text.split("\n") if line.strip()]
        first_line = lines[0] if lines else "Полезная запись"
        # Очищаем markdown символы из заголовка
        clean_title = first_line.replace("*", "").replace("#", "").replace("_", "").strip()[:40]

    fav_id = await add_favorite(
        user_id=user_id,
        category=category,
        title=clean_title,
        content=message_text
    )

    await callback.answer("⭐ Успешно сохранено в Избранное!", show_alert=True)
    # Заменяем клавиатуру под сообщением, чтобы было видно, что оно уже сохранено
    await callback.message.edit_reply_markup(
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="✅ Сохранено в Избранное ⭐", callback_data="noop")]
            ]
        )
    )


@router.callback_query(F.data == "noop")
async def noop_handler(callback: types.CallbackQuery):
    """Пустой клик по уже сохраненному элементу."""
    await callback.answer("Эта запись уже в вашем избранном!")


@router.message(F.text == "⭐ Моё избранное")
@router.message(Command("favorites"))
async def show_favorites_menu(message: types.Message):
    """Отображение списка сохраненных записей в Избранном."""
    favs = await get_favorites(message.from_user.id)
    if not favs:
        await message.answer(
            "⭐ **Ваше Избранное пока пусто.**\n\n"
            "Когда бот составит вам меню, вкусный рецепт или рассчитает КБЖУ — "
            "просто нажмите кнопку **«⭐ Сохранить в избранное»** под сообщением, "
            "и оно появится здесь!",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        return

    await message.answer(
        f"⭐ **Ваше Избранное (сохранено {len(favs)}):**\n"
        "Выберите запись для просмотра деталей:",
        reply_markup=get_favorites_list_keyboard(favs),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "fav_back_list")
async def back_to_favorites_list(callback: types.CallbackQuery):
    """Возврат к списку избранного."""
    await callback.answer()
    favs = await get_favorites(callback.from_user.id)
    if not favs:
        await callback.message.edit_text("⭐ В вашем избранном пока ничего нет.")
        return

    await callback.message.edit_text(
        f"⭐ **Ваше Избранное (сохранено {len(favs)}):**\n"
        "Выберите запись для просмотра деталей:",
        reply_markup=get_favorites_list_keyboard(favs),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("fav_view_"))
async def view_favorite_item(callback: types.CallbackQuery):
    """Просмотр конкретной сохраненной записи."""
    fav_id = int(callback.data.replace("fav_view_", ""))
    fav = await get_favorite_by_id(fav_id, callback.from_user.id)

    if not fav:
        await callback.answer("Запись не найдена или была удалена.", show_alert=True)
        return

    await callback.answer()
    content = fav.get("content", "")
    created_at = fav.get("created_at", "")
    title = fav.get("title", "Запись")

    header = f"📌 **{title}** _(сохранено: {created_at})_\n\n"
    full_text = header + content
    category = fav.get("category", "")

    # Если это список покупок, формируем ссылку для мгновенной пересылки супругу/супруге
    share_url = ""
    share_text = ""
    if category == "shopping" or "список покупок" in title.lower() or "список покупок" in content.lower():
        share_url = f"https://t.me/share/url?url=https://t.me&text={urllib.parse.quote(content)}"
        share_text = content

    chunks = [full_text[i:i + 4000] for i in range(0, len(full_text), 4000)]
    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            await callback.message.answer(
                chunk,
                reply_markup=get_favorite_item_keyboard(fav_id, share_url=share_url, share_text=share_text),
                parse_mode="Markdown"
            )
        else:
            await callback.message.answer(chunk, parse_mode="Markdown")


@router.callback_query(F.data.startswith("fav_del_"))
async def delete_favorite_item(callback: types.CallbackQuery):
    """Удаление записи из избранного."""
    fav_id = int(callback.data.replace("fav_del_", ""))
    deleted = await delete_favorite(fav_id, callback.from_user.id)

    if deleted:
        await callback.answer("🗑️ Запись удалена из избранного!", show_alert=True)
    else:
        await callback.answer("⚠️ Не удалось удалить запись.", show_alert=True)

    # Обновляем список
    favs = await get_favorites(callback.from_user.id)
    if not favs:
        await callback.message.edit_text(
            "⭐ В вашем избранном больше нет записей.",
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            f"⭐ **Ваше Избранное (сохранено {len(favs)}):**\n"
            "Выберите запись для просмотра деталей:",
            reply_markup=get_favorites_list_keyboard(favs),
            parse_mode="Markdown"
        )
