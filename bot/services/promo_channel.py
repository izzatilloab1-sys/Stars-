"""
Promokod kanal posti (Variant B).

Admin promokod yaratib, uni kanalga post qilishi mumkin:
  - Bot kanalga post yuboradi: ADMIN MATNI + pastda avto hisoblagich qatori.
  - Foydalanuvchi kanalда kodni ko'radi -> BOTGA yozadi -> Stars/so'm oladi.
  - Har redeem'dan keyin kanaldagi post hisoblagichi editMessageText bilan yangilanadi.

Hisoblagich: "🎁 Qolgan: <qolgan>/<limit>" (limit tugasa "❌ Tugadi").
Admin matni o'zgarmaydi — faqat pastdagi hisoblagich + kod qatori.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_post_text(channel_text: str, code: str, used_count: int, max_uses: int) -> str:
    """Kanal post matnini tuzadi: admin matni + kod + hisoblagich."""
    remaining = max(max_uses - used_count, 0)
    if remaining > 0:
        counter = (
            f"\n\n🎁 Promokod: <code>{code}</code>\n"
            f"📊 Qolgan: <b>{remaining}/{max_uses}</b> "
            f"(ishlatilgan: {used_count})\n"
            f"👉 Kodni botga yuboring va bonusni oling!"
        )
    else:
        counter = (
            f"\n\n🎁 Promokod: <s>{code}</s>\n"
            f"❌ <b>Tugadi!</b> Barcha {max_uses} ta ishlatildi."
        )
    return (channel_text or "").rstrip() + counter


async def send_channel_post(bot, chat_id: str, channel_text: str, code: str,
                            used_count: int, max_uses: int):
    """Kanalga promokod postini yuboradi. (message_id, None) yoki (None, xato) qaytaradi."""
    text = build_post_text(channel_text, code, used_count, max_uses)
    try:
        msg = await bot.send_message(chat_id, text)
        return msg.message_id, None
    except Exception as e:  # noqa: BLE001
        logger.warning("Kanal postini yuborishda xatolik: %s", e)
        return None, str(e)


async def update_channel_post(bot, promo) -> None:
    """Kanaldagi post hisoblagichini yangilaydi (redeem'dan keyin).

    promo — Promocode obyekti (channel_chat_id, channel_message_id, channel_text,
    code, used_count, max_uses bo'lishi kerak). Xato bo'lsa jimgina yutadi."""
    if not promo or not promo.channel_chat_id or not promo.channel_message_id:
        return
    text = build_post_text(
        promo.channel_text or "", promo.code, promo.used_count, promo.max_uses
    )
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=promo.channel_chat_id,
            message_id=promo.channel_message_id,
        )
    except Exception as e:  # noqa: BLE001
        # Post o'chirilган / bot admin emas / matn o'zgarmagan — redeem baribir muvaffaqiyatli
        logger.info("Kanal postini yangilab bo'lmadi (e'tiborsiz): %s", e)
