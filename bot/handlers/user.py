"""Foydalanuvchi handlerlari: /start, profil, referal, promokod, buyurtmalar."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.database import db
from bot.keyboards.kb import cancel_kb, main_menu
from bot.utils.states import PromoState

router = Router()


async def _is_admin(user_id: int) -> bool:
    """Admin: .env ADMIN_IDS, DB adminlar yoki owner."""
    if user_id in settings.admin_id_list:
        return True
    if user_id in await db.get_db_admins():
        return True
    owner = await db.get_owner()
    return owner is not None and user_id == owner


def _parse_ref(args: str | None) -> int | None:
    """start=ref_123 ko'rinishidagi argumentdan referrer ID ni oladi."""
    if not args:
        return None
    args = args.strip()
    if args.startswith("ref_"):
        args = args[4:]
    return int(args) if args.isdigit() else None


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    referrer_id = _parse_ref(command.args)

    user, created = await db.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        referrer_id=referrer_id,
    )

    # Yangi foydalanuvchi referal orqali kelgan bo'lsa, referrerga xabar
    if created and user.referrer_id:
        try:
            await message.bot.send_message(
                user.referrer_id,
                f"🎉 Sizning havolangiz orqali yangi foydalanuvchi qo'shildi: "
                f"{message.from_user.full_name}\n"
                f"U birinchi buyurtma qilganda sizga bonus beriladi!",
            )
        except Exception:  # noqa: BLE001
            pass

    price = await db.get_price_per_star()
    await message.answer(
        f"👋 Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n\n"
        f"⭐ Bu bot orqali istalgan Telegram foydalanuvchisiga <b>Telegram Stars</b> "
        f"sotib olishingiz mumkin.\n\n"
        f"💰 Narx: <b>{price:,} so'm</b> / 1 Star\n"
        f"📦 Minimal buyurtma: {settings.min_stars} Stars\n\n"
        f"Quyidagi menyudan kerakli bo'limni tanlang 👇",
        reply_markup=main_menu(await _is_admin(message.from_user.id)),
    )


@router.message(F.text == "👤 Profil")
async def profile(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start bosing.")
        return
    refs = await db.count_referrals(user.id)
    await message.answer(
        f"👤 <b>Profil</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💰 Bonus balans: <b>{user.balance:,} so'm</b>\n"
        f"👥 Taklif qilganlar: <b>{refs} ta</b>\n",
    )


@router.message(F.text == "👥 Referal")
async def referral(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start bosing.")
        return
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{user.id}"
    refs = await db.count_referrals(user.id)
    ref_stars = await db.get_referral_stars()
    if ref_stars > 0:
        reward_line = (
            f"Do'stlaringizni taklif qiling — ularning har biri birinchi buyurtma "
            f"qilganda sizga <b>{ref_stars} Stars</b> qiymatida bonus beriladi! ⭐"
        )
    else:
        reward_line = (
            f"Do'stlaringizni taklif qiling va ular buyurtma qilganda "
            f"<b>{settings.referral_bonus_percent}%</b> bonus oling!"
        )
    await message.answer(
        f"👥 <b>Referal dasturi</b>\n\n"
        f"{reward_line}\n\n"
        f"🔗 Sizning havolangiz:\n<code>{link}</code>\n\n"
        f"👤 Taklif qilganlaringiz: <b>{refs} ta</b>\n"
        f"💰 Jami bonus balans: <b>{user.balance:,} so'm</b>",
    )


@router.message(F.text == "📦 Buyurtmalarim")
async def my_orders(message: Message):
    orders = await db.get_user_orders(message.from_user.id)
    if not orders:
        await message.answer("Sizda hali buyurtmalar yo'q.")
        return
    status_emoji = {
        "pending": "⏳", "paid": "💳", "delivering": "🚚",
        "done": "✅", "failed": "❌", "refunded": "↩️",
    }
    lines = ["📦 <b>Oxirgi buyurtmalaringiz:</b>\n"]
    for o in orders:
        em = status_emoji.get(o.status.value, "•")
        lines.append(
            f"{em} #{o.id} — {o.stars:,} ⭐ → @{o.target_username} "
            f"({o.amount:,} so'm) [{o.status.value}]"
        )
    await message.answer("\n".join(lines))


@router.message(F.text == "ℹ️ Yordam")
async def help_msg(message: Message):
    await message.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "1️⃣ «⭐ Stars sotib olish» tugmasini bosing\n"
        "2️⃣ Stars yuborilishi kerak bo'lgan @username ni kiriting\n"
        "3️⃣ Miqdorni kiriting\n"
        "4️⃣ To'lov usulini tanlab, to'lovni amalga oshiring\n"
        "5️⃣ Stars avtomatik yetkaziladi ✅\n\n"
        "❓ Muammo bo'lsa, administratorga murojaat qiling."
    )


# ---------- Promokod ----------
@router.message(F.text == "🎁 Promokod")
async def promo_start(message: Message, state: FSMContext):
    await state.set_state(PromoState.code)
    await message.answer("🎁 Promokodni kiriting:", reply_markup=cancel_kb())


@router.message(PromoState.code)
async def promo_redeem(message: Message, state: FSMContext):
    code = message.text.strip()
    ok, msg, _ = await db.redeem_promocode(message.from_user.id, code)
    await state.clear()
    await message.answer(("✅ " if ok else "❌ ") + msg, reply_markup=main_menu())


@router.callback_query(F.data == "cancel")
async def cancel_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.answer()
