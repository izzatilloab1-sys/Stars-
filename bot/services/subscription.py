"""Majburiy obuna (forced subscription) uchun yordamchi funksiyalar.

`missing_required_channels` — foydalanuvchi hali obuna bo'lmagan faol majburiy
kanallar ro'yxatini qaytaradi. Telegram API xatolari (bot kanalda admin emas,
kanal topilmadi) BLOKLAMAYDI: bunday kanal o'tkazib yuboriladi va ogohlantirish
log qilinadi — shunda noto'g'ri sozlangan kanal hamma foydalanuvchini bloklab
qo'ymaydi.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot.database import db
from bot.database.models import RequiredChannel

logger = logging.getLogger(__name__)

# getChatMember: obuna hisoblanadigan statuslar
_SUBSCRIBED_STATUSES = ("member", "administrator", "creator", "owner")


def _chat_id(channel_id: str) -> int | str:
    """'-100...' kabi raqamli ID'ni int'ga, @username'ni o'zgarishsiz qaytaradi."""
    if isinstance(channel_id, str) and channel_id.lstrip("-").isdigit():
        return int(channel_id)
    return channel_id


async def missing_required_channels(bot: Bot, user_id: int) -> list[RequiredChannel]:
    """Foydalanuvchi obuna bo'lishi kerak bo'lgan, lekin hali bo'lmagan kanallar.

    Faol majburiy kanallar bo'lmasa — bo'sh ro'yxat qaytaradi (hech qanday
    o'zgarish yo'q). API xatosi bo'lgan kanal bloklamaydi (o'tkazib yuboriladi).
    """
    channels = await db.get_active_required_channels()
    missing: list[RequiredChannel] = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=_chat_id(ch.channel_id), user_id=user_id
            )
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            # Bot kanalda admin emas yoki kanal topilmadi — bloklamaymiz
            logger.warning(
                "Majburiy obuna tekshiruvi o'tkazib yuborildi (kanal=%s): %s",
                ch.channel_id, e,
            )
            continue
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Majburiy obuna tekshiruvida kutilmagan xatolik (kanal=%s): %s",
                ch.channel_id, e,
            )
            continue
        status = getattr(member, "status", None)
        status = getattr(status, "value", status)  # enum bo'lsa qiymatini olamiz
        if status not in _SUBSCRIBED_STATUSES:
            missing.append(ch)
    return missing
