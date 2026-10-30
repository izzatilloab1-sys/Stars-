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


async def get_receive_address() -> str:
    """To'lovlar keladigan TON manzilini qaytaradi.

    Tartib:
      1. Admin panelda alohida o'rnatilgan manzil (DB 'ton_wallet_address')
      2. .env dagi TON_WALLET_ADDRESS
      3. Ulangan hamyon seed'idan hisoblangan manzil (eng qulay — alohida
         sozlash shart emas, seed ulangan bo'lsa yetarli)
    Topilmasa bo'sh satr."""
    from bot.database import db

    # 1 & 2: DB sozlama -> .env
    addr = await db.get_setting("ton_wallet_address", settings.ton_wallet_address)
    if addr:
        return addr

    # 3: ulangan seed'dan hisoblaymiz (hamyon versiyasini hisobga olib)
    try:
        from bot.services.fragment import get_wallet_address
        seed_addr = await get_wallet_address()
        if seed_addr:
            return seed_addr
    except Exception as e:  # noqa: BLE001
        logger.warning("Seed'dan manzil olishda xatolik: %s", e)
    return ""


async def get_ton_uzs_rate() -> float:
    """1 TON necha so'm turishini qaytaradi.

    Avval admin panelda o'rnatilgan kurs (DB sozlama 'ton_uzs_rate') tekshiriladi:
    agar u > 0 bo'lsa, aynan o'sha qiymat qaytariladi.
    Aks holda TON->USD coingecko'dan olinadi, USD->UZS esa .env dagi USD_UZS_RATE dan.
    Agar API ishlamasa, .env dagi TON_UZS_FALLBACK ishlatiladi.
    """
    # Admin tomonidan o'rnatilgan kursni birinchi o'ringa qo'yamiz (lazy import -> sirkular importdan qochish)
    try:
        from bot.database import db
        admin_rate = await db.get_ton_uzs_rate_setting()
        if admin_rate and admin_rate > 0:
            return float(admin_rate)
    except Exception as e:  # noqa: BLE001
        logger.warning("Admin TON kursini o'qishda xatolik: %s. API ga o'tilmoqda.", e)

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
    address = await get_receive_address()
    if not address:
        logger.error("TON qabul qilish manzili aniqlanmadi (seed/.env/admin yo'q).")
        return None

    headers = {}
    if settings.ton_api_key:
        headers["X-API-Key"] = settings.ton_api_key

    params = {
        "account": address,
        "limit": 30,
        "offset": 0,
        "sort": "desc",
    }
    logger.info("TON tekshiruv: manzil=%s, kutilgan comment=%r, min_nano=%s",
                address, comment, min_nano)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{TONCENTER_V3}/transactions",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("toncenter javobi: %s | %s", resp.status, body[:300])
                    return None
                data = await resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("toncenter so'rovida xatolik: %s", e)
        return None

    txs = data.get("transactions", [])
    logger.info("TON tekshiruv: %s ta tranzaksiya topildi", len(txs))

    for tx in txs:
        in_msg = tx.get("in_msg") or {}
        # faqat tashqaridan kelgan (incoming) to'lov: manba bo'lishi kerak
        if not in_msg.get("source"):
            continue
        value = int(in_msg.get("value") or 0)
        msg_comment = _extract_comment(in_msg)
        logger.info("  kelgan to'lov: comment=%r, value=%s nano", msg_comment, value)
        # Comment mos (bo'sh joy/katta-kichik harf farqini e'tiborga olmaymiz)
        comment_ok = msg_comment and msg_comment.strip().lower() == comment.strip().lower()
        if comment_ok and value >= min_nano:
            logger.info("  ✅ MOS KELDI -> tasdiqlanadi")
            return tx.get("hash")
        elif comment_ok and value < min_nano:
            logger.warning("  ⚠️ comment mos, lekin summa kam: %s < %s nano", value, min_nano)
    return None


def _extract_comment(in_msg: dict) -> str | None:
    """in_msg ichidan matnli comment'ni ajratib oladi (toncenter v3 turli formatlar)."""
    # 1) message_content.decoded.comment yoki .text
    mc = in_msg.get("message_content") or {}
    decoded = mc.get("decoded")
    if isinstance(decoded, dict):
        for key in ("comment", "text"):
            val = decoded.get(key)
            if val:
                return str(val).strip()
    if isinstance(decoded, str) and decoded.strip():
        return decoded.strip()
    # 2) to'g'ridan-to'g'ri comment/message maydoni
    for key in ("comment", "message"):
        val = in_msg.get(key)
        if val:
            return str(val).strip()
    return None
