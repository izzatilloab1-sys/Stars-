"""To'lov usulini tanlash, to'lovni tekshirish va Stars yetkazish."""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.config import settings
from bot.database import db
from bot.database.models import OrderStatus
from bot.keyboards.kb import admin_delivery_kb, check_payment_kb, main_menu
from bot.services import payment as pay_service
from bot.services import ton_payment
from bot.services.fragment import deliver_stars

logger = logging.getLogger(__name__)
router = Router()


# ---------- To'lov usuli tanlandi ----------
@router.callback_query(F.data.startswith("pay:"))
async def choose_payment(call: CallbackQuery, state: FSMContext):
    _, method, order_id_s = call.data.split(":")
    order_id = int(order_id_s)
    order = await db.get_order(order_id)
    if not order or order.status != OrderStatus.PENDING:
        await call.answer("Buyurtma topilmadi yoki allaqachon yakunlangan.", show_alert=True)
        return

    # --- Bonus balansdan to'lash ---
    if method == "balance":
        user = await db.get_user(call.from_user.id)
        if not user or user.balance < order.amount:
            await call.answer(
                f"Balans yetarli emas. Kerak: {order.amount:,} so'm, "
                f"bor: {user.balance if user else 0:,} so'm.",
                show_alert=True,
            )
            return
        # atomik: faqat PENDING bo'lsa PAID qilamiz, so'ng balansdan yechamiz
        if not await db.mark_paid_if_pending(order_id):
            await call.answer("Bu buyurtma allaqachon to'langan.", show_alert=True)
            return
        await db.add_balance(user.id, -order.amount)
        await db.set_order_field(order_id, payment_method="balance")
        await call.message.edit_text(
            f"✅ Buyurtma #{order_id} bonus balansdan to'landi!\n⏳ Stars yetkazilmoqda..."
        )
        await state.clear()
        await _deliver_and_finish(call.bot, order_id)
        return

    # --- TON orqali to'lov ---
    if method == "ton":
        await _start_ton_payment(call, order)
        return

    # --- Click / Payme (so'm) ---
    if method == "click":
        url = pay_service.build_click_url(order_id, order.amount)
    elif method == "payme":
        url = pay_service.build_payme_url(order_id, order.amount)
    else:
        await call.answer("Noma'lum usul.", show_alert=True)
        return

    await db.set_order_field(order_id, payment_method=method)

    await call.message.edit_text(
        f"🧾 <b>Buyurtma #{order_id}</b>\n"
        f"⭐ {order.stars:,} Stars → @{order.target_username}\n"
        f"💵 To'lov: <b>{order.amount:,} so'm</b> ({method.title()})\n\n"
        f"1️⃣ «To'lash» tugmasi orqali to'lovni amalga oshiring\n"
        f"2️⃣ So'ng «To'ladim / Tekshirish» tugmasini bosing",
        reply_markup=check_payment_kb(order_id, url),
    )
    await call.answer()


async def _start_ton_payment(call: CallbackQuery, order):
    """TON to'lov ko'rsatmalarini chiqaradi: manzil + aniq summa + comment."""
    if not settings.ton_wallet_address:
        await call.answer("TON to'lovi hozircha sozlanmagan. Boshqa usulni tanlang.", show_alert=True)
        return

    comment = f"SB{order.id}"  # unikal memo
    ton_amount = await ton_payment.uzs_to_ton(order.amount)
    await db.set_order_field(order.id, payment_method="ton", pay_comment=comment)

    addr = settings.ton_wallet_address
    # ton:// deep-link (Tonkeeper va boshqa hamyonlar ochadi)
    nano = int(ton_amount * 1e9)
    ton_url = f"https://app.tonkeeper.com/transfer/{addr}?amount={nano}&text={comment}"

    await call.message.edit_text(
        f"💎 <b>TON orqali to'lov — Buyurtma #{order.id}</b>\n\n"
        f"⭐ {order.stars:,} Stars → @{order.target_username}\n"
        f"💵 Summa: <b>{order.amount:,} so'm</b> ≈ <b>{ton_amount} TON</b>\n\n"
        f"📥 <b>Manzil:</b>\n<code>{addr}</code>\n\n"
        f"💬 <b>Izoh (comment/memo) — MAJBURIY:</b>\n<code>{comment}</code>\n\n"
        f"⚠️ Summani va <b>izohni</b> aynan ko'rsatilgandek yuboring, aks holda to'lov "
        f"topilmaydi. To'lovdan so'ng «Tekshirish» tugmasini bosing.",
        reply_markup=check_payment_kb(order.id, ton_url),
    )
    await call.answer()


# ---------- To'lovni tekshirish ----------
@router.callback_query(F.data.startswith("check:"))
async def check_payment(call: CallbackQuery):
    order_id = int(call.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi.", show_alert=True)
        return
    if order.status != OrderStatus.PENDING:
        await call.answer("Bu buyurtma allaqachon to'langan yoki yakunlangan.", show_alert=True)
        return

    method = order.payment_method or ""
    payment_id = None

    if method == "ton":
        # Blokcheyndan to'lovni tekshiramiz
        await call.answer("⏳ Blokcheyn tekshirilmoqda...", show_alert=False)
        min_nano = await ton_payment.uzs_to_nano_ton(order.amount)
        # kurs tebranishi uchun 3% bardoshlilik
        min_nano = int(min_nano * 0.97)
        tx_hash = await ton_payment.check_ton_payment(order.pay_comment or "", min_nano)
        if not tx_hash:
            await call.answer(
                "⏳ TON to'lovi hali topilmadi.\n\n"
                "Tranzaksiya tasdiqlanishi 1-2 daqiqa olishi mumkin. "
                "Summa va izoh (comment) to'g'ri ekanini tekshirib, birozdan so'ng qayta urinib ko'ring.",
                show_alert=True,
            )
            return
        payment_id = tx_hash
    else:
        # Click / Payme — webhook orqali tasdiqlangan bo'lishi kerak
        paid = await pay_service.verify_payment(order_id, method)
        if not paid:
            await call.answer(
                "⏳ To'lov hali tasdiqlanmadi.\n\n"
                "Agar to'lagan bo'lsangiz, bir oz kuting va qayta tekshiring. "
                "To'lov provayder webhook'i orqali avtomatik tasdiqlanadi.",
                show_alert=True,
            )
            return

    # Atomik: faqat PENDING -> PAID bo'lsa yetkazamiz (ikki marta bosishdan himoya)
    first = await db.mark_paid_if_pending(order_id, payment_id)
    if not first:
        await call.answer("Bu buyurtma allaqachon to'langan.", show_alert=True)
        return
    await call.message.edit_text(
        f"✅ To'lov tasdiqlandi! Buyurtma #{order_id}\n⏳ Stars yetkazilmoqda..."
    )
    await call.answer()
    await _deliver_and_finish(call.bot, order_id)


# ---------- Yetkazish ----------
async def _deliver_and_finish(bot: Bot, order_id: int):
    """To'langan buyurtmani yetkazadi.

    Eslatma: referal bonusi FAQAT Stars ko'rinishida va referal belgilangan
    sonli zadaniyani bajargach beriladi (bot.database.db.maybe_reward_referrer_for_tasks,
    'Stars ishlash' oqimida chaqiriladi). Shuning uchun bu yerda eski so'm asosidagi
    apply_referral_bonus CHAQIRILMAYDI — aks holda referrer ikki marta mukofotlanardi.
    """
    order = await db.get_order(order_id)
    if not order:
        return

    await db.set_order_status(order_id, OrderStatus.DELIVERING)
    delivery = await deliver_stars(order.target_username, order.stars)

    if delivery.ok:
        await db.set_order_status(order_id, OrderStatus.DONE, payment_id=delivery.tx_id)
        try:
            await bot.send_message(
                order.user_id,
                f"🎉 Buyurtma #{order_id} bajarildi!\n"
                f"⭐ {order.stars:,} Stars @{order.target_username} ga yuborildi.",
                reply_markup=main_menu(),
            )
        except Exception:  # noqa: BLE001
            pass
    else:
        # manual rejim yoki xatolik -> adminga yuboramiz
        for admin_id in settings.admin_id_list:
            try:
                await bot.send_message(
                    admin_id,
                    f"🚚 <b>Yangi yetkazish</b>\n"
                    f"Buyurtma #{order_id}\n"
                    f"⭐ {order.stars:,} Stars → @{order.target_username}\n"
                    f"👤 Mijoz: <code>{order.user_id}</code>\n"
                    f"💵 {order.amount:,} so'm\n\n"
                    f"ℹ️ {delivery.message}",
                    reply_markup=admin_delivery_kb(order_id),
                )
            except Exception:  # noqa: BLE001
                pass
        try:
            await bot.send_message(
                order.user_id,
                f"⏳ Buyurtma #{order_id} qabul qilindi va tez orada yetkaziladi. "
                f"Rahmat!",
                reply_markup=main_menu(),
            )
        except Exception:  # noqa: BLE001
            pass
