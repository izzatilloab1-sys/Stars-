"""Middleware'lar."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.database import db


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
