"""Middleware'lar."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.database import db
from bot.keyboards.kb import MENU_BUTTONS


class MenuResetMiddleware(BaseMiddleware):
    """Asosiy menyu tugmasi bosilganda faol FSM holatini tozalaydi.

    Bu outer middleware sifatida ulanadi — shuning uchun u FSM holatidagi
    handler filtri tekshirilishidan OLDIN ishlaydi. Natijada foydalanuvchi
    bir oqim (masalan Stars sotib olish) o'rtasida boshqa menyu tugmasini
    bossa (masalan Balans to'ldirish), eski holat bekor qilinib, yangi
    buyruq to'g'ri ishlaydi.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.text in MENU_BUTTONS:
            state: FSMContext | None = data.get("state")
            if state is not None and await state.get_state() is not None:
                await state.clear()
        return await handler(event, data)


class BanMiddleware(BaseMiddleware):
    """Banlangan foydalanuvchilarni to'xtatadi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            db_user = await db.get_user(user.id)
            if db_user and db_user.is_banned:
                if isinstance(event, Message):
                    await event.answer("🚫 Siz bloklangansiz.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Siz bloklangansiz.", show_alert=True)
                return
        return await handler(event, data)
