"""
To'lov provayderlari: Click va Payme uchun invoice/link generatsiya va
tekshirish uchun yordamchi funksiyalar.

ESLATMA: Click va Payme real integratsiyasi ularning merchant kabineti,
callback (webhook) URL va imzo tekshiruvini talab qiladi. To'liq avtomatik
tasdiqlash uchun alohida webhook server (masalan aiohttp) kerak bo'ladi.

Bu modul:
  - To'lov havolasini (payment link) yaratadi.
  - Sinov/manual tasdiqlash uchun `verify_payment` interfeysini beradi.

Prodakshnda `verify_payment` o'rniga webhook orqali kelgan tasdiqni ishlating.
"""
from __future__ import annotations

import hashlib
import time
import urllib.parse

from bot.config import settings


def build_click_url(order_id: int, amount: int) -> str:
    """Click to'lov havolasini yaratadi (shahsiy sahifa usuli)."""
    params = {
        "service_id": settings.click_service_id,
        "merchant_id": settings.click_merchant_id,
        "amount": amount,
        "transaction_param": order_id,
    }
    query = urllib.parse.urlencode(params)
    return f"https://my.click.uz/services/pay?{query}"


def build_payme_url(order_id: int, amount: int) -> str:
    """Payme to'lov havolasini yaratadi (base64 ko'rinishidagi parametrlar)."""
    import base64

    # Payme tiyin hisobida ishlaydi (1 so'm = 100 tiyin)
    payload = (
        f"m={settings.payme_merchant_id};"
        f"ac.order_id={order_id};"
        f"a={amount * 100}"
    )
    encoded = base64.b64encode(payload.encode()).decode()
    return f"https://checkout.paycom.uz/{encoded}"


def click_signature(order_id: int, amount: int, action: int, sign_time: str) -> str:
    """Click callback imzosini hisoblaydi (webhook tomonida tekshirish uchun)."""
    raw = (
        f"{settings.click_service_id}{order_id}{settings.click_secret_key}"
        f"{amount}{action}{sign_time}"
    )
    return hashlib.md5(raw.encode()).hexdigest()


async def verify_payment(order_id: int, method: str) -> bool:
    """
    Click/Payme to'lovini tekshirish.

    Click va Payme to'lovlari webhook (bot/webhook.py) orqali avtomatik
    tasdiqlanadi — webhook kelganda buyurtma statusi PAID ga o'zgaradi va
    Stars yetkazish o'sha yerda ishga tushadi.

    Bu funksiya foydalanuvchi «Tekshirish» tugmasini bosganda chaqiriladi va
    buyurtma allaqachon webhook orqali to'langanmi, shuni tekshiradi.
    """
    from bot.database import db
    from bot.database.models import OrderStatus

    order = await db.get_order(order_id)
    if not order:
        return False
    return order.status in (
        OrderStatus.PAID,
        OrderStatus.DELIVERING,
        OrderStatus.DONE,
    )
