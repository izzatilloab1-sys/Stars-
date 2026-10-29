"""Balans to'ldirish oqimi: summa -> to'lov usuli (TON/Click/Payme) -> tasdiq."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.database import db
from bot.database.models import OrderStatus
from bot.keyboards.kb import (
    cancel_kb,
    check_payment_kb,
    topup_amount_kb,
    topup_payment_kb,
)
from bot.services import payment as pay_service
from bot.services import ton_payment

router = Router()


class TopupState(StatesGroup):
    custom_amount = State()


MIN_TOPUP = 10_000  # minimal to'ldirish summasi (so'm)


@router.message(F.text == "💳 Balans to'ldirish")
async def topup_start(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    bal = user.balance if user else 0
    await message.answer(
        f"💳 <b>Balans to'ldirish</b>\n\n"
        f"💰 Joriy balans: <b>{bal:,} so'm</b>\n\n"
        f"To'ldirmoqchi bo'lgan summani tanlang yoki kiriting 👇",
        reply_markup=topup_amount_kb(),
    )


@router.callback_query(F.data.startswith("topup:"))
async def topup_amount(call: CallbackQuery, state: FSMContext):
    part = call.data.split(":")[1]
    if part == "custom":
        await state.set_state(TopupState.custom_amount)
        await call.message.answer(
            f"✏️ Summani kiriting (minimal {MIN_TOPUP:,} so'm):", reply_markup=cancel_kb()
        )
        await call.answer()
        return
    amount = int(part)
    await _show_topup_methods(call.message, amount, edit=True)
    await call.answer()


@router.message(TopupState.custom_amount)
async def topup_custom(message: Message, state: FSMContext):
    text = message.text.strip().replace(" ", "")
    if not text.isdigit():
        await message.answer("❌ Faqat son kiriting:")
        return
    amount = int(text)
    if amount < MIN_TOPUP:
        await message.answer(f"❌ Minimal {MIN_TOPUP:,} so'm.")
        return
    await state.clear()
    await _show_topup_methods(message, amount, edit=False)


async def _show_topup_methods(message, amount: int, edit: bool):
    text = (
        f"💳 <b>Balans to'ldirish</b>\n\n"
        f"💵 Summa: <b>{amount:,} so'm</b>\n\n"
        f"To'lov usulini tanlang 👇"
    )
    kb = topup_payment_kb(amount)
    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("tpay:"))
async def topup_pay(call: CallbackQuery, state: FSMContext):
    _, method, amount_s = call.data.split(":")
    amount = int(amount_s)
    topup = await db.create_topup(call.from_user.id, amount, method)

    if method == "ton":
        if not settings.ton_wallet_address:
            await call.answer("TON to'lovi sozlanmagan.", show_alert=True)
            return
        comment = f"TP{topup.id}"
        ton_amount = await ton_payment.uzs_to_ton(amount)
        await db.set_topup_field(topup.id, pay_comment=comment)
        addr = settings.ton_wallet_address
        nano = int(ton_amount * 1e9)
        ton_url = f"https://app.tonkeeper.com/transfer/{addr}?amount={nano}&text={comment}"
        await call.message.edit_text(
            f"💎 <b>TON orqali balans to'ldirish #{topup.id}</b>\n\n"
            f"💵 {amount:,} so'm ≈ <b>{ton_amount} TON</b>\n\n"
            f"📥 <b>Manzil:</b>\n<code>{addr}</code>\n\n"
            f"💬 <b>Izoh (MAJBURIY):</b>\n<code>{comment}</code>\n\n"
            f"⚠️ Summa va izohni aynan yuboring. So'ng «Tekshirish» bosing.",
            reply_markup=check_payment_kb_topup(topup.id, ton_url),
        )
        await call.answer()
        return

    # Click / Payme
    if method == "click":
        url = pay_service.build_click_url(topup.id, amount)
    else:
        url = pay_service.build_payme_url(topup.id, amount)
    await call.message.edit_text(
        f"💳 <b>Balans to'ldirish #{topup.id}</b>\n\n"
        f"💵 {amount:,} so'm ({method.title()})\n\n"
        f"1️⃣ «To'lash» tugmasini bosing\n"
        f"2️⃣ So'ng «Tekshirish» tugmasini bosing",
        reply_markup=check_payment_kb_topup(topup.id, url),
    )
    await call.answer()


def check_payment_kb_topup(topup_id: int, pay_url: str | None = None):
    """Balans to'ldirish uchun tekshirish klaviaturasi (order emas, topup)."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    kb = InlineKeyboardBuilder()
    if pay_url:
        kb.row(InlineKeyboardButton(text="💳 To'lash", url=pay_url))
    kb.row(InlineKeyboardButton(text="✅ To'ladim / Tekshirish", callback_data=f"tcheck:{topup_id}"))
    kb.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))
    return kb.as_markup()


@router.callback_query(F.data.startswith("tcheck:"))
async def topup_check(call: CallbackQuery):
    topup_id = int(call.data.split(":")[1])
    topup = await db.get_topup(topup_id)
    if not topup:
        await call.answer("Topilmadi.", show_alert=True)
        return
    if topup.status != OrderStatus.PENDING:
        await call.answer("Bu to'ldirish allaqachon yakunlangan.", show_alert=True)
        return

    payment_id = None
    if topup.payment_method == "ton":
        await call.answer("⏳ Blokcheyn tekshirilmoqda...")
        min_nano = await ton_payment.uzs_to_nano_ton(topup.amount)
        min_nano = int(min_nano * 0.97)
        tx = await ton_payment.check_ton_payment(topup.pay_comment or "", min_nano)
        if not tx:
            await call.answer(
                "⏳ TON to'lovi hali topilmadi. Birozdan so'ng qayta urinib ko'ring.",
                show_alert=True,
            )
            return
        payment_id = tx
    else:
        # Click/Payme webhook orqali topup'ni to'g'ridan-to'g'ri PAID qiladi
        if topup.status == OrderStatus.PENDING:
            await call.answer(
                "⏳ To'lov hali tasdiqlanmadi. Provayder webhook'i orqali avtomatik tasdiqlanadi.",
                show_alert=True,
            )
            return

    ok = await db.complete_topup_if_pending(topup_id, payment_id)
    if not ok:
        await call.answer("Bu to'ldirish allaqachon hisobga olingan.", show_alert=True)
        return
    user = await db.get_user(call.from_user.id)
    await call.message.edit_text(
        f"✅ Balans to'ldirildi! +{topup.amount:,} so'm\n"
        f"💰 Yangi balans: <b>{user.balance:,} so'm</b>"
    )
    await call.answer("✅ Muvaffaqiyatli!")
