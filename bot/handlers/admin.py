"""Admin panel: statistika, promokod, balans qo'shish, broadcast, yetkazishni tasdiqlash."""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from bot.config import settings
from bot.database import db
from bot.database.models import OrderStatus, User
from bot.keyboards.kb import account_menu, admin_menu, main_menu
from bot.services import fragment as fragment_service
from bot.utils.states import AdminState

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_id_list


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 <b>Admin panel</b>", reply_markup=admin_menu())


@router.callback_query(F.data == "adm:stats")
async def adm_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    s = await db.get_stats()
    await call.message.edit_text(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['users']:,}</b>\n"
        f"📦 Buyurtmalar: <b>{s['orders']:,}</b>\n"
        f"⭐ Yetkazilgan Stars: <b>{s['stars_sold']:,}</b>\n"
        f"💰 Tushum (to'langan): <b>{s['revenue']:,} so'm</b>",
        reply_markup=admin_menu(),
    )
    await call.answer()


# ---------- Promokod yaratish ----------
@router.callback_query(F.data == "adm:promo")
async def adm_promo_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.promo_code)
    await call.message.answer("🎁 Promokod nomini kiriting (masalan: NEWYEAR2026):")
    await call.answer()


@router.message(AdminState.promo_code)
async def adm_promo_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(code=message.text.strip())
    await state.set_state(AdminState.promo_bonus)
    await message.answer("💰 Bonus miqdorini kiriting (so'mda):")


@router.message(AdminState.promo_bonus)
async def adm_promo_bonus(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Son kiriting:")
        return
    await state.update_data(bonus=int(message.text.strip()))
    await state.set_state(AdminState.promo_uses)
    await message.answer("🔢 Nechta marta ishlatilsin? (son):")


@router.message(AdminState.promo_uses)
async def adm_promo_uses(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Son kiriting:")
        return
    data = await state.get_data()
    try:
        promo = await db.create_promocode(
            code=data["code"], bonus_amount=data["bonus"], max_uses=int(message.text.strip())
        )
    except Exception as e:  # noqa: BLE001
        await state.clear()
        await message.answer(f"❌ Xatolik (ehtimol bunday kod bor): {e}")
        return
    await state.clear()
    await message.answer(
        f"✅ Promokod yaratildi!\n\n"
        f"🎁 Kod: <code>{promo.code}</code>\n"
        f"💰 Bonus: {promo.bonus_amount:,} so'm\n"
        f"🔢 Limit: {promo.max_uses} marta",
    )


# ---------- Balans qo'shish ----------
@router.callback_query(F.data == "adm:addbal")
async def adm_addbal_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.add_balance_user)
    await call.message.answer("👤 Foydalanuvchi ID sini kiriting:")
    await call.answer()


@router.message(AdminState.add_balance_user)
async def adm_addbal_user(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ ID son bo'lishi kerak:")
        return
    await state.update_data(uid=int(message.text.strip()))
    await state.set_state(AdminState.add_balance_amount)
    await message.answer("💰 Qo'shiladigan summani kiriting (manfiy ham bo'lishi mumkin):")


@router.message(AdminState.add_balance_amount)
async def adm_addbal_amount(message: Message, state: FSMContext):
    text = message.text.strip().replace("+", "")
    try:
        amount = int(text)
    except ValueError:
        await message.answer("❌ Son kiriting:")
        return
    data = await state.get_data()
    uid = data["uid"]
    user = await db.get_user(uid)
    if not user:
        await state.clear()
        await message.answer("❌ Bunday foydalanuvchi topilmadi.")
        return
    await db.add_balance(uid, amount)
    await state.clear()
    await message.answer(f"✅ {uid} ga {amount:,} so'm qo'shildi.")
    action_word = "qo'shildi" if amount >= 0 else "yechildi"
    try:
        await message.bot.send_message(
            uid, f"💰 Balansingizga {amount:,} so'm {action_word}."
        )
    except Exception:  # noqa: BLE001
        pass


# ---------- Broadcast ----------
@router.callback_query(F.data == "adm:broadcast")
async def adm_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.broadcast)
    await call.message.answer("📢 Yubormoqchi bo'lgan xabaringizni yozing:")
    await call.answer()


@router.message(AdminState.broadcast)
async def adm_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    async with db.Session() as s:
        res = await s.execute(select(User.id).where(User.is_banned == False))  # noqa: E712
        ids = [row[0] for row in res.all()]

    sent, failed = 0, 0
    for uid in ids:
        try:
            await message.copy_to(uid)
            sent += 1
        except Exception:  # noqa: BLE001
            failed += 1
    await message.answer(f"📢 Yuborildi: {sent} ta\n❌ Yuborilmadi: {failed} ta")


# ---------- Yetkazishni tasdiqlash (manual rejim) ----------
@router.callback_query(F.data.startswith("deliver:"))
async def deliver_action(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    _, action, order_id_s = call.data.split(":")
    order_id = int(order_id_s)
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi.", show_alert=True)
        return

    if action == "done":
        await db.set_order_status(order_id, OrderStatus.DONE)
        await call.message.edit_text(call.message.html_text + "\n\n✅ <b>Yetkazildi</b>")
        try:
            await bot.send_message(
                order.user_id,
                f"🎉 Buyurtma #{order_id} bajarildi!\n"
                f"⭐ {order.stars:,} Stars @{order.target_username} ga yuborildi.",
                reply_markup=main_menu(),
            )
        except Exception:  # noqa: BLE001
            pass
    elif action == "refund":
        await db.set_order_status(order_id, OrderStatus.REFUNDED)
        # pulni bonus balansga qaytaramiz
        await db.add_balance(order.user_id, order.amount)
        await call.message.edit_text(call.message.html_text + "\n\n↩️ <b>Qaytarildi</b>")
        try:
            await bot.send_message(
                order.user_id,
                f"↩️ Buyurtma #{order_id} bekor qilindi. "
                f"{order.amount:,} so'm bonus balansingizga qaytarildi.",
                reply_markup=main_menu(),
            )
        except Exception:  # noqa: BLE001
            pass
    await call.answer()


# ==================== AKKAUNT ULASH ====================
@router.callback_query(F.data == "adm:back")
async def adm_back(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.message.edit_text("🛠 <b>Admin panel</b>", reply_markup=admin_menu())
    await call.answer()


async def _account_text(status: dict) -> str:
    seed = "✅ ulangan" if status["seed_set"] else "❌ ulanmagan"
    if status["seed_set"]:
        seed += f" ({status['seed_words']} so'z)"
    cookie = "✅ ulangan" if status["cookie_set"] else "❌ ulanmagan"
    addr = status.get("wallet_address") or "—"
    mode = "🟢 fragment (avtomatik)" if status["mode"] == "fragment" else "🟡 manual (qo'lda)"
    return (
        f"🔗 <b>Akkaunt ulash</b>\n\n"
        f"Bu yerda Fragment akkauntingizni (cookie) va TON hamyoningizni (seed) "
        f"ulaysiz. Ulangandan so'ng bot SHU akkaunt va hamyondan foydalanib "
        f"Stars'ni avtomatik sotib oladi.\n\n"
        f"🔑 Hamyon seed: {seed}\n"
        f"🍪 Fragment cookie: {cookie}\n"
        f"📥 Hamyon manzili: <code>{addr}</code>\n"
        f"⚙️ Rejim: {mode}\n\n"
        f"⚠️ <b>Diqqat:</b> seed va cookie — maxfiy ma'lumot. Ularni faqat o'zingiz "
        f"ishonadigan botga kiriting."
    )


@router.callback_query(F.data == "adm:account")
async def adm_account(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    status = await fragment_service.get_account_status()
    await call.message.edit_text(await _account_text(status), reply_markup=account_menu(status))
    await call.answer()


# ---------- Seed kiritish ----------
@router.callback_query(F.data == "acc:seed")
async def acc_seed_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.set_seed)
    await call.message.answer(
        "🔑 TON hamyon seed iborasini kiriting (12 yoki 24 so'z, probel bilan).\n\n"
        "⚠️ Bu hamyon Stars uchun to'lov manbai bo'ladi — unda yetarli TON bo'lsin.\n"
        "Xavfsizlik uchun yuborgach, xabaringizni o'chirib qo'ying."
    )
    await call.answer()


@router.message(AdminState.set_seed)
async def acc_seed_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    seed = message.text.strip()
    words = seed.split()
    if len(words) not in (12, 24):
        await message.answer("❌ Seed 12 yoki 24 so'zdan iborat bo'lishi kerak. Qayta kiriting:")
        return
    await db.set_setting("ton_wallet_mnemonic", seed)
    await state.clear()
    # himoya: foydalanuvchi xabarini o'chirishga urinamiz
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
    addr = await fragment_service.get_wallet_address(seed)
    await message.answer(
        f"✅ Hamyon seed saqlandi ({len(words)} so'z).\n"
        f"📥 Manzil: <code>{addr or '—'}</code>\n\n"
        f"(Xavfsizlik uchun seed yuborilgan xabaringiz o'chirildi.)"
    )
    status = await fragment_service.get_account_status()
    await message.answer(await _account_text(status), reply_markup=account_menu(status))


# ---------- Cookie kiritish (4 qadam) ----------
@router.callback_query(F.data == "acc:cookie")
async def acc_cookie_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.set_cookie_token)
    await call.message.answer(
        "🍪 <b>Fragment cookie'larini kiritamiz (4 qadam).</b>\n\n"
        "Qanday olish:\n"
        "1️⃣ Brauzerda fragment.com ga kiring, Telegram orqali login qiling\n"
        "2️⃣ TON hamyoningizni ulang (Connect TON)\n"
        "3️⃣ F12 → Application → Cookies → fragment.com\n\n"
        "Endi <b>stel_token</b> qiymatini yuboring:"
    )
    await call.answer()


@router.message(AdminState.set_cookie_token)
async def acc_cookie_token(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("fragment_stel_token", message.text.strip())
    await state.set_state(AdminState.set_cookie_ssid)
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
    await message.answer("✅ stel_token saqlandi.\n\nEndi <b>stel_ssid</b> ni yuboring:")


@router.message(AdminState.set_cookie_ssid)
async def acc_cookie_ssid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("fragment_stel_ssid", message.text.strip())
    await state.set_state(AdminState.set_cookie_dt)
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
    await message.answer("✅ stel_ssid saqlandi.\n\nEndi <b>stel_dt</b> ni yuboring:")


@router.message(AdminState.set_cookie_dt)
async def acc_cookie_dt(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("fragment_stel_dt", message.text.strip())
    await state.set_state(AdminState.set_cookie_ton)
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
    await message.answer("✅ stel_dt saqlandi.\n\nEndi <b>stel_ton_token</b> ni yuboring:")


@router.message(AdminState.set_cookie_ton)
async def acc_cookie_ton(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await db.set_setting("fragment_stel_ton_token", message.text.strip())
    await state.clear()
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
    await message.answer("✅ Barcha Fragment cookie'lari saqlandi!")
    status = await fragment_service.get_account_status()
    await message.answer(await _account_text(status), reply_markup=account_menu(status))


# ---------- Rejimni almashtirish ----------
@router.callback_query(F.data == "acc:mode")
async def acc_mode_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    current = await fragment_service.get_fragment_mode()
    new_mode = "manual" if current == "fragment" else "fragment"
    await db.set_setting("fragment_mode", new_mode)
    status = await fragment_service.get_account_status()
    await call.message.edit_text(await _account_text(status), reply_markup=account_menu(status))
    await call.answer(f"Rejim: {new_mode}")


# ---------- Balansni tekshirish ----------
@router.callback_query(F.data == "acc:balance")
async def acc_balance(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer("⏳ Tekshirilmoqda...")
    bal = await fragment_service.get_wallet_balance()
    if bal is None:
        await call.message.answer("❌ Balansni olishning iloji bo'lmadi (seed ulanmagan yoki tarmoq xatosi).")
    else:
        await call.message.answer(f"💎 Ulangan hamyon balansi: <b>{bal} TON</b>")


# ---------- Akkauntni uzish ----------
@router.callback_query(F.data == "acc:clear")
async def acc_clear(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    for key in (
        "ton_wallet_mnemonic", "fragment_stel_token", "fragment_stel_ssid",
        "fragment_stel_dt", "fragment_stel_ton_token",
    ):
        await db.set_setting(key, "")
    await db.set_setting("fragment_mode", "manual")
    status = await fragment_service.get_account_status()
    await call.message.edit_text(await _account_text(status), reply_markup=account_menu(status))
    await call.answer("🗑 Akkaunt uzildi, rejim manual'ga o'tdi.")
