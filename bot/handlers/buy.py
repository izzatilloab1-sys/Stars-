"""Stars sotib olish oqimi: username -> miqdor -> tasdiq -> to'lov usuli."""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.database import db
from bot.keyboards.kb import cancel_kb, main_menu, payment_methods_kb
from bot.utils.states import BuyStars

router = Router()

USERNAME_RE = re.compile(r"^@?[A-Za-z0-9_]{4,32}$")


@router.message(F.text == "⭐ Stars sotib olish")
async def buy_start(message: Message, state: FSMContext):
    await state.set_state(BuyStars.target)
    await message.answer(
        "👤 Stars kimga yuborilsin?\n\n"
        "Telegram <b>@username</b> ni kiriting (masalan: <code>@durov</code>).\n"
        "O'zingizga olmoqchi bo'lsangiz, o'z username'ingizni yozing.",
        reply_markup=cancel_kb(),
    )


@router.message(BuyStars.target)
async def buy_target(message: Message, state: FSMContext):
    username = message.text.strip()
    if not USERNAME_RE.match(username):
        await message.answer(
            "❌ Noto'g'ri username. Faqat harf, raqam va _ ishlatilishi mumkin "
            "(4–32 belgi). Qayta kiriting:"
        )
        return
    username = username.lstrip("@")
    await state.update_data(target=username)
    await state.set_state(BuyStars.amount)
    await message.answer(
        f"✅ Qabul qiluvchi: <b>@{username}</b>\n\n"
        f"⭐ Nechta Stars sotib olmoqchisiz?\n"
        f"(min {settings.min_stars:,}, max {settings.max_stars:,})",
        reply_markup=cancel_kb(),
    )


@router.message(BuyStars.amount)
async def buy_amount(message: Message, state: FSMContext):
    text = message.text.strip().replace(" ", "")
    if not text.isdigit():
        await message.answer("❌ Iltimos, faqat son kiriting:")
        return
    stars = int(text)
    if stars < settings.min_stars:
        await message.answer(f"❌ Minimal {settings.min_stars:,} Stars.")
        return
    if stars > settings.max_stars:
        await message.answer(f"❌ Maksimal {settings.max_stars:,} Stars.")
        return

    amount = stars * settings.price_per_star
    data = await state.get_data()
    target = data["target"]

    # Buyurtma yaratamiz (PENDING)
    order = await db.create_order(
        user_id=message.from_user.id,
        target_username=target,
        stars=stars,
        amount=amount,
        bonus_used=0,
        payment_method="",
    )
    await state.update_data(order_id=order.id, amount=amount, stars=stars)
    await state.set_state(BuyStars.confirm)

    user = await db.get_user(message.from_user.id)
    bonus_note = ""
    if user and user.balance > 0:
        bonus_note = f"\n💰 Bonus balansingiz: {user.balance:,} so'm (to'lovda ishlatsangiz bo'ladi)"

    await message.answer(
        f"🧾 <b>Buyurtma #{order.id}</b>\n\n"
        f"👤 Qabul qiluvchi: <b>@{target}</b>\n"
        f"⭐ Miqdor: <b>{stars:,} Stars</b>\n"
        f"💵 Narx: <b>{amount:,} so'm</b>"
        f"{bonus_note}\n\n"
        f"To'lov usulini tanlang 👇",
        reply_markup=payment_methods_kb(order.id),
    )


@router.callback_query(F.data == "cancel", BuyStars.target)
@router.callback_query(F.data == "cancel", BuyStars.amount)
@router.callback_query(F.data == "cancel", BuyStars.confirm)
async def buy_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Buyurtma bekor qilindi.")
    await call.message.answer("Asosiy menyu:", reply_markup=main_menu())
    await call.answer()
