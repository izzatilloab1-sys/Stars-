"""
Avtomatik so'm to'lovi — Telethon listener ("Aniq summa + Telegram bildirishnomasi").

G'oya (YTT/pullik xizmatsiz, 100% tekin):
  1. User balans to'ldirishda summa tanlaydi (masalan 20 000 so'm).
  2. Bot unga NOYOB summa beradi: 20 000 + (1..99) = masalan 20 037 so'm,
     va buni 15 daqiqaga pending ro'yxatiga (Topup, payment_method='card') yozadi.
  3. User kartaga AYNAN 20 037 so'm tashlaydi (izoh shart emas, istalgan ilovadan).
  4. Kartaga ulangan Telegram akkauntga bank bildirishnomasi keladi
     (@ClickUz, @payme, @humocardbot, bank SMS->Telegram va h.k.):
        "Пополнение: +20 037 UZS" / "Kirim: 20037 so'm" ...
  5. Bu listener (shaxsiy akkauntga Telethon orqali ulangan) xabarni tutadi,
     matndan KIRIM summasini regex bilan ajratadi va pending Topup'ni topib,
     userning so'm balansini AVTOMATIK oshiradi.

Listener bot bilan BIR process'da, fon vazifasi sifatida ishlaydi (main.py).
Shaxsiy akkaunt session'i admin panel / .env orqali ulanadi (tg_account.py).
"""
from __future__ import annotations

import logging
import re

from bot.config import settings

logger = logging.getLogger(__name__)

# Kirim (pul tushishi) summasini topish uchun regex'lar.
# Turli banklar/ilovalar matni har xil, shuning uchun bir nechta namuna.
# Faqat KIRIM (+, Пополнение, Kirim, Vneseno) xabarlarini qabul qilamiz;
# chiqim (-, Oplata, Spisanie) e'tiborga olinmaydi.
_INCOME_HINTS = re.compile(
    r"(попол|posto|kirim|kelib|vneseno|приход|\bprixod\b|zачисл|\+\s*\d)",
    re.IGNORECASE,
)
_OUTCOME_HINTS = re.compile(
    r"(списан|оплата|spisan|oplata|chiqim|to['`]?lov amalga|\-\s*\d)",
    re.IGNORECASE,
)
# Summani topish: "20 037", "20037.00", "20,037" + UZS/so'm/сум
_AMOUNT_RE = re.compile(
    r"([0-9][0-9\s.,]{2,15}?)\s*(?:uzs|so['`]?m|сум|сўм|сom)?",
    re.IGNORECASE,
)


def extract_income_amount(text: str) -> int | None:
    """Bank bildirishnomasi matnidan KIRIM summasini (butun so'm) ajratadi.

    Chiqim (spisanie/oplata) xabarlari e'tiborga olinmaydi. Topilmasa None."""
    if not text:
        return None
    # Chiqim bo'lsa — rad etamiz
    if _OUTCOME_HINTS.search(text) and not _INCOME_HINTS.search(text):
        return None

    # Barcha sonlarni topib, eng kattasini (odatda summa) olamiz.
    # "20 037", "20,037", "20037.00" kabi formatlarni normallashtiramiz.
    candidates: list[int] = []
    for raw in re.findall(r"[0-9][0-9\s.,]{2,15}", text):
        cleaned = raw.strip().replace(" ", "").replace(",", "")
        # kasr qismini tashlaymiz (20037.00 -> 20037)
        if "." in cleaned:
            cleaned = cleaned.split(".")[0]
        if cleaned.isdigit():
            val = int(cleaned)
            if 1_000 <= val <= 100_000_000:  # mantiqiy summa oralig'i
                candidates.append(val)
    if not candidates:
        return None
    return max(candidates)


async def _bank_sender_ids() -> set[str]:
    """Qaysi yuboruvchilardan (username yoki id) xabar qabul qilinsin.

    Admin panel / .env dagi vergul bilan ajratilgan ro'yxat. Bo'sh bo'lsa —
    hamma yuboruvchidan (lekin baribir summa + pending mosligi tekshiriladi)."""
    from bot.database import db
    raw = await db.get_setting("bank_senders", settings.bank_senders)
    return {x.strip().lstrip("@").lower() for x in raw.split(",") if x.strip()}


async def _process_notification(text: str, sender: str | None, bot) -> None:
    """Bitta bank bildirishnomasini qayta ishlaydi."""
    from bot.database import db

    amount = extract_income_amount(text)
    if amount is None:
        return

    topup = await db.find_card_topup_by_amount(amount)
    if not topup:
        logger.info("Karta to'lovi: %s so'm keldi, lekin mos pending topup topilmadi.", amount)
        return

    # Atomik: faqat PENDING -> PAID, balansga asosiy summa qo'shiladi (ikki marta emas)
    ok = await db.complete_topup_if_pending(topup.id, payment_id=f"card:{amount}")
    if not ok:
        return

    user = await db.get_user(topup.user_id)
    new_balance = user.balance if user else topup.amount
    logger.info("✅ Avto karta to'lovi: #%s, %s so'm, user %s", topup.id, amount, topup.user_id)
    try:
        await bot.send_message(
            topup.user_id,
            f"✅ <b>To'lovingiz qabul qilindi!</b>\n\n"
            f"💵 Tushgan summa: {amount:,} so'm\n"
            f"💰 Hisobingizga qo'shildi: +{topup.amount:,} so'm\n"
            f"💳 Yangi balans: <b>{new_balance:,} so'm</b>",
        )
    except Exception:  # noqa: BLE001
        pass
    # Adminlarga ham xabar (ixtiyoriy nazorat)
    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(
                admin_id,
                f"💵 Avto to'lov: #{topup.id} | {amount:,} so'm | "
                f"user <code>{topup.user_id}</code>",
            )
        except Exception:  # noqa: BLE001
            pass


async def start_payment_listener(bot) -> None:
    """Telethon listener'ni ishga tushiradi (main.py fon vazifasi sifatida chaqiradi).

    Shaxsiy akkaunt session'i ulanmagan bo'lsa — jimgina chiqadi (avto karta
    to'lovi o'chiq, boshqa funksiyalar ishlayveradi)."""
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession

    from bot.services.tg_account import _creds, get_session

    session_str = await get_session()
    if not session_str:
        logger.warning(
            "Avto karta to'lovi: Telegram akkaunt (session) ulanmagan — listener ishga tushmadi. "
            "Admin panel -> Akkaunt ulash orqali ulang."
        )
        return

    api_id, api_hash = await _creds()
    if not api_id or not api_hash:
        logger.warning("Avto karta to'lovi: api_id/api_hash yo'q — listener ishga tushmadi.")
        return

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    allowed = await _bank_sender_ids()

    @client.on(events.NewMessage(incoming=True))
    async def _handler(event):  # noqa: ANN001
        try:
            text = event.message.message or ""
            # Yuboruvchini aniqlaymiz (username yoki id)
            sender_name = None
            try:
                sender = await event.get_sender()
                sender_name = (getattr(sender, "username", None) or str(getattr(sender, "id", ""))).lower()
            except Exception:  # noqa: BLE001
                sender_name = None

            # Agar oq ro'yxat belgilangan bo'lsa, faqat o'shalardan qabul qilamiz
            if allowed and sender_name and sender_name not in allowed:
                return
            await _process_notification(text, sender_name, bot)
        except Exception:  # noqa: BLE001
            logger.exception("Karta to'lovi xabarini qayta ishlashda xatolik")

    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning("Avto karta to'lovi: session eskirgan — listener ishga tushmadi.")
            return
        me = await client.get_me()
        logger.info(
            "✅ Avto karta to'lovi listener ishga tushdi: @%s (bank yuboruvchilar: %s)",
            getattr(me, "username", me.id), allowed or "hamma",
        )
        # Fonda doimiy tinglaydi
        await client.run_until_disconnected()
    except Exception:  # noqa: BLE001
        logger.exception("Payment listener ishga tushirishda xatolik")
