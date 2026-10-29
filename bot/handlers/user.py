"""Foydalanuvchi handlerlari: /start, profil, referal, promokod, buyurtmalar."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.database import db
from bot.keyboards.kb import cancel_kb, main_menu, tasks_list_kb
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
        f"⭐ Bonus Stars: <b>{user.stars_balance}</b>\n"
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
    threshold = await db.get_referral_task_threshold()
    if ref_stars > 0:
        reward_line = (
            f"Do'stlaringizni taklif qiling! Taklif qilgan odamingiz "
            f"<b>{threshold} ta zadaniya</b> (Stars ishlash) bajarsa, sizga "
            f"<b>{ref_stars} ⭐</b> bonus beriladi."
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
        f"⭐ Bonus Stars: <b>{user.stars_balance}</b>\n"
        f"💰 Bonus balans: <b>{user.balance:,} so'm</b>",
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


# ---------- Stars ishlash (zadaniya) ----------
@router.message(F.text == "🌟 Stars ishlash")
async def earn_stars(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, /start bosing.")
        return
    tasks = await db.get_active_tasks()
    # foydalanuvchi allaqachon bajargan zadaniyalarni chiqarib tashlaymiz
    available = []
    for t in tasks:
        if not await db.has_completed_task(t.id, message.from_user.id):
            available.append(t)
    if not available:
        await message.answer(
            "🌟 <b>Stars ishlash</b>\n\n"
            "Hozircha siz uchun yangi zadaniya yo'q. Keyinroq qayta tekshiring! 😊\n\n"
            f"⭐ Sizning Stars balansingiz: <b>{user.stars_balance}</b>"
        )
        return
    await message.answer(
        "🌟 <b>Stars ishlash</b>\n\n"
        "Quyidagi kanallarga obuna bo'ling va «✅ Tekshirish» tugmasini bosing — "
        "obuna tasdiqlansa, Stars hisobingizga qo'shiladi.\n\n"
        f"⭐ Sizning Stars balansingiz: <b>{user.stars_balance}</b>",
        reply_markup=tasks_list_kb(available),
    )


@router.callback_query(F.data.startswith("task:check:"))
async def task_check(call: CallbackQuery, bot: Bot):
    task_id = int(call.data.split(":")[2])
    task = await db.get_task(task_id)
    if not task or not task.is_active:
        await call.answer("Bu zadaniya mavjud emas.", show_alert=True)
        return
    if await db.has_completed_task(task_id, call.from_user.id):
        await call.answer("Siz bu zadaniyani allaqachon bajargansiz.", show_alert=True)
        return

    chat_id: int | str = (
        int(task.channel_id)
        if isinstance(task.channel_id, str) and task.channel_id.lstrip("-").isdigit()
        else task.channel_id
    )
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=call.from_user.id)
    except (TelegramBadRequest, TelegramForbiddenError):
        await call.answer(
            "❌ Obunani tekshirib bo'lmadi. Iltimos, administratorga murojaat qiling "
            "(bot kanalda admin bo'lishi kerak).",
            show_alert=True,
        )
        return

    status = getattr(member, "status", None)
    status = getattr(status, "value", status)  # enum bo'lsa qiymatini olamiz
    subscribed = status in ("member", "administrator", "creator", "owner")
    if not subscribed:
        await call.answer(
            "❌ Siz hali obuna bo'lmagansiz. Avval kanalga obuna bo'ling, keyin qayta tekshiring.",
            show_alert=True,
        )
        return

    credited = await db.complete_task_if_new(task_id, call.from_user.id, task.reward_stars)
    if not credited:
        await call.answer("Siz bu zadaniyani allaqachon bajargansiz.", show_alert=True)
        return

    balance = await db.get_stars_balance(call.from_user.id)
    await call.answer(f"✅ +{task.reward_stars} ⭐ qo'shildi!", show_alert=True)
    try:
        await call.message.answer(
            f"🎉 Zadaniya bajarildi! <b>+{task.reward_stars} ⭐</b> qo'shildi.\n"
            f"⭐ Umumiy Stars balansingiz: <b>{balance}</b>"
        )
    except Exception:  # noqa: BLE001
        pass

    # Referal zadaniya chegarasi bonusi
    reward = await db.maybe_reward_referrer_for_tasks(call.from_user.id)
    if reward:
        referrer_id, reward_stars = reward
        try:
            await bot.send_message(
                referrer_id,
                f"🎉 +{reward_stars} ⭐ (referalingiz "
                f"{await db.count_user_task_completions(call.from_user.id)} ta zadaniya bajardi)",
            )
        except Exception:  # noqa: BLE001
            pass


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
