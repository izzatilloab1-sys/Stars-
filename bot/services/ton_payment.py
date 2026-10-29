"""
TON orqali to'lov qabul qilish va tekshirish.

Oqim:
  1. Foydalanuvchi buyurtma qiladi -> bot TON manzilini va UNIKAL comment (memo) beradi.
     comment = buyurtma identifikatori (masalan "SB<order_id>" yoki tasodifiy kod).
  2. Foydalanuvchi o'z TON hamyonidan ko'rsatilgan summani ayni o'sha comment bilan yuboradi.
  3. Bot toncenter API v3 orqali hamyonga kelgan tranzaksiyalarni tekshiradi va
     kerakli comment + summa topilsa, to'lovni tasdiqlaydi.

TON narxi dinamik bo'lgani uchun so'mdagi summa -> TON ga aylantiriladi.
Kurs TON/USD coingecko'dan, USD/UZS esa konfiguratsiyadan olinadi (yoki API).
"""
from __future__ import annotations

import logging

import aiohttp

from bot.config import settings

logger = logging.getLogger(__name__)

TONCENTER_V3 = "https://toncenter.com/api/v3"
COINGECKO = "https://api.coingecko.com/api/v3/simple/price"


async def get_ton_uzs_rate() -> float:
    """1 TON necha so'm turishini qaytaradi.

    TON->USD coingecko'dan olinadi, USD->UZS esa .env dagi USD_UZS_RATE dan.
    Agar API ishlamasa, .env dagi TON_UZS_FALLBACK ishlatiladi.
    """
    try:
        async with aiohttp.ClientSession() as session:
            params = {"ids": "the-open-network", "vs_currencies": "usd"}
            async with session.get(COINGECKO, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                ton_usd = float(data["the-open-network"]["usd"])
                return ton_usd * settings.usd_uzs_rate
    except Exception as e:  # noqa: BLE001
        logger.warning("TON kursini olishda xatolik: %s. Fallback ishlatilmoqda.", e)
        return float(settings.ton_uzs_fallback)


async def uzs_to_nano_ton(amount_uzs: int) -> int:
    """So'mdagi summani nanoton (1 TON = 1e9 nanoton) ga aylantiradi."""
    rate = await get_ton_uzs_rate()
    ton_amount = amount_uzs / rate
    return int(ton_amount * 1e9)


async def uzs_to_ton(amount_uzs: int) -> float:
    rate = await get_ton_uzs_rate()
    return round(amount_uzs / rate, 4)


async def check_ton_payment(comment: str, min_nano: int) -> str | None:
    """
    Hamyonga kelgan tranzaksiyalar orasidan `comment` bilan va kamida `min_nano`
    miqdoridagi incoming to'lovni qidiradi.

    Qaytaradi: tranzaksiya hash (topilsa) yoki None.
    """
    if not settings.ton_wallet_address:
        logger.error("TON_WALLET_ADDRESS sozlanmagan.")
        return None

    headers = {}
    if settings.ton_api_key:
        headers["X-API-Key"] = settings.ton_api_key

    params = {
        "account": settings.ton_wallet_address,
        "limit": 30,
        "offset": 0,
        "sort": "desc",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{TONCENTER_V3}/transactions",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning("toncenter javobi: %s", resp.status)
                    return None
                data = await resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("toncenter so'rovida xatolik: %s", e)
        return None

    for tx in data.get("transactions", []):
        in_msg = tx.get("in_msg") or {}
        # faqat tashqaridan kelgan (incoming) to'lov: manba bo'lishi kerak
        if not in_msg.get("source"):
            continue
        value = int(in_msg.get("value") or 0)
        # comment decoded_body yoki message_content.decoded ichida bo'ladi
        msg_comment = _extract_comment(in_msg)
        if msg_comment == comment and value >= min_nano:
            return tx.get("hash")
    return None


def _extract_comment(in_msg: dict) -> str | None:
    """in_msg ichidan matnli comment'ni ajratib oladi (v3 formati)."""
    # v3: message_content.decoded.comment
    mc = in_msg.get("message_content") or {}
    decoded = mc.get("decoded") or {}
    if isinstance(decoded, dict):
        comment = decoded.get("comment")
        if comment:
            return str(comment).strip()
    # ba'zi javoblarda to'g'ridan-to'g'ri
    comment = in_msg.get("comment")
    if comment:
        return str(comment).strip()
    return None
