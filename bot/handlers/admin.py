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
from bot.keyboards.kb import account_menu, admin_menu, main_menu, tg_account_menu
from bot.services import fragment as fragment_service
from bot.services import tg_account
from bot.utils.states import AdminState

logger = logging.getLogger(__name__)
router = Router()


async def is_admin(user_id: int) -> bool:
    """Admin: .env ADMIN_IDS, DB'dagi adminlar yoki owner."""
    if user_id in settings.admin_id_list:
        return True
    if user_id in await db.get_db_admins():
        return True
    owner = await db.get_owner()
    return owner is not None and user_id == owner


async def is_owner(user_id: int) -> bool:
    """Owner: settings['owner'], o'rnatilmagan bo'lsa .env'dagi BIRINCHI admin."""
    owner = await db.get_owner()
    if owner is not None:
        return user_id == owner
    # owner hali o'rnatilmagan: .env'dagi birinchi admin owner hisoblanadi
    admins = settings.admin_id_list
    return bool(admins) and user_id == admins[0]


@router.message(Command("admin"))
@router.message(F.text == "🛠 Admin panel")
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return
    owner = await is_owner(message.from_user.id)
    await message.answer("🛠 <b>Admin panel</b>", reply_markup=admin_menu(owner))


@router.callback_query(F.data == "adm:stats")
async def adm_stats(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
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
    if not await is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.promo_code)
    await call.message.answer("🎁 Promokod nomini kiriting (masalan: NEWYEAR2026):")
    await call.answer()


@router.message(AdminState.promo_code)
async def adm_promo_code(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(call.from_user.id):
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
    if not await is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.broadcast)
    await call.message.answer("📢 Yubormoqchi bo'lgan xabaringizni yozing:")
    await call.answer()


@router.message(AdminState.broadcast)
async def adm_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(call.from_user.id):
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
    if not await is_admin(call.from_user.id):
        return
    await state.clear()
    owner = await is_owner(call.from_user.id)
    await call.message.edit_text("🛠 <b>Admin panel</b>", reply_markup=admin_menu(owner))
    await call.answer()


@router.callback_query(F.data == "noop")
async def noop_cb(call: CallbackQuery):
    await call.answer()


# ==================== NARX / REFERAL SOZLAMALARI ====================
async def _settings_text() -> str:
    price = await db.get_price_per_star()
    ref_stars = await db.get_referral_stars()
    ref_line = (
        f"{ref_stars} Stars" if ref_stars > 0
        else f"o'chirilgan (foizli rejim: {settings.referral_bonus_percent}%)"
    )
    return (
        f"⚙️ <b>Narx va referal sozlamalari</b>\n\n"
        f"💰 1 Star narxi: <b>{price:,} so'm</b>\n"
        f"👥 1 referalga mukofot: <b>{ref_line}</b>\n\n"
        f"ℹ️ Narxni o'zgartirsangiz, barcha yangi buyurtmalar yangi narxda hisoblanadi.\n"
        f"Referal Stars > 0 bo'lsa, har yangi referal birinchi buyurtma qilganda "
        f"shuncha Stars qiymatida (Stars × narx) bonus beradi."
    )


@router.callback_query(F.data == "adm:settings")
async def adm_settings(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return
    await state.clear()
    from bot.keyboards.kb import settings_menu
    await call.message.edit_text(await _settings_text(), reply_markup=settings_menu())
    await call.answer()


@router.callback_query(F.data == "set:price")
async def set_price_start(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.set_price)
    await call.message.answer("💰 1 ta Star'ning yangi narxini kiriting (so'mda, faqat son):")
    await call.answer()


@router.message(AdminState.set_price)
async def set_price_save(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    text = message.text.strip().replace(" ", "")
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Musbat son kiriting:")
        return
    await db.set_price_per_star(int(text))
    await state.clear()
    from bot.keyboards.kb import settings_menu
    await message.answer(f"✅ 1 Star narxi {int(text):,} so'm qilib o'rnatildi.")
    await message.answer(await _settings_text(), reply_markup=settings_menu())


@router.callback_query(F.data == "set:refstars")
async def set_refstars_start(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.set_ref_stars)
    await call.message.answer(
        "👥 1 ta referal uchun necha Stars mukofot berilsin? (son)\n\n"
        "0 kiritsangiz — foizli rejimga qaytadi."
    )
    await call.answer()


@router.message(AdminState.set_ref_stars)
async def set_refstars_save(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    text = message.text.strip().replace(" ", "")
    if not text.isdigit():
        await message.answer("❌ Son kiriting (0 yoki undan katta):")
        return
    await db.set_referral_stars(int(text))
    await state.clear()
    from bot.keyboards.kb import settings_menu
    await message.answer(f"✅ Referal mukofoti {int(text)} Stars qilib o'rnatildi.")
    await message.answer(await _settings_text(), reply_markup=settings_menu())


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
    if not await is_admin(call.from_user.id):
        return
    await state.clear()
    status = await fragment_service.get_account_status()
    await call.message.edit_text(await _account_text(status), reply_markup=account_menu(status))
    await call.answer()


# ---------- Seed kiritish ----------
@router.callback_query(F.data == "acc:seed")
async def acc_seed_start(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
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
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(call.from_user.id):
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
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(call.from_user.id):
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
    if not await is_admin(call.from_user.id):
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
    if not await is_admin(call.from_user.id):
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


# ==================== TELEGRAM AKKAUNT (telefon raqam orqali) ====================
# Faol login oqimlari: admin_id -> LoginFlow
_login_flows: dict[int, "tg_account.LoginFlow"] = {}


async def _tg_text(status: dict) -> str:
    api = "✅ sozlangan" if status.get("tg_api_set") else "❌ sozlanmagan"
    tg = "❌ ulanmagan"
    if status.get("tg_set"):
        info = await tg_account.check_session()
        if info.get("ok"):
            tg = f"✅ @{info.get('username') or info.get('id')} ({info.get('name','')})"
        else:
            tg = f"⚠️ ulangan, lekin ishlamayapti: {info.get('error','')}"
    return (
        f"📱 <b>Telegram akkaunt ulash</b>\n\n"
        f"Telefon raqamingiz orqali Telegram akkauntingizni ulaysiz. Bu akkaunt "
        f"Fragment'da Stars sotib olish uchun ishlatiladi.\n\n"
        f"🔧 api_id / api_hash: {api}\n"
        f"👤 Akkaunt: {tg}\n\n"
        f"ℹ️ api_id / api_hash <a href='https://my.telegram.org'>my.telegram.org</a> → "
        f"API development tools dan olinadi (bepul).\n\n"
        f"⚠️ <b>Diqqat:</b> session — maxfiy ma'lumot, akkauntingizga to'liq kirish beradi."
    )


@router.callback_query(F.data == "acc:tg")
async def acc_tg(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return
    await state.clear()
    status = await fragment_service.get_account_status()
    await call.message.edit_text(
        await _tg_text(status), reply_markup=tg_account_menu(status), disable_web_page_preview=True
    )
    await call.answer()


# ---------- api_id / api_hash ----------
@router.callback_query(F.data == "tg:api")
async def tg_api_start(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.tg_api_id)
    await call.message.answer("🔧 <b>api_id</b> ni kiriting (son, my.telegram.org dan):")
    await call.answer()


@router.message(AdminState.tg_api_id)
async def tg_api_id_save(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❌ api_id son bo'lishi kerak. Qayta kiriting:")
        return
    await db.set_setting("tg_api_id", message.text.strip())
    await state.set_state(AdminState.tg_api_hash)
    await message.answer("🔧 Endi <b>api_hash</b> ni kiriting:")


@router.message(AdminState.tg_api_hash)
async def tg_api_hash_save(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await db.set_setting("tg_api_hash", message.text.strip())
    await state.clear()
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
    await message.answer("✅ api_id / api_hash saqlandi.")
    status = await fragment_service.get_account_status()
    await message.answer(await _tg_text(status), reply_markup=tg_account_menu(status),
                         disable_web_page_preview=True)


# ---------- Raqam orqali ulash ----------
@router.callback_query(F.data == "tg:phone")
async def tg_phone_start(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return
    status = await fragment_service.get_account_status()
    if not status.get("tg_api_set"):
        await call.answer("Avval api_id / api_hash ni sozlang.", show_alert=True)
        return
    await state.set_state(AdminState.tg_phone)
    await call.message.answer(
        "📞 Telefon raqamingizni xalqaro formatda kiriting (masalan: <code>+998901234567</code>):"
    )
    await call.answer()


@router.message(AdminState.tg_phone)
async def tg_phone_submit(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    phone = message.text.strip().replace(" ", "")
    flow = tg_account.LoginFlow()
    try:
        await flow.start(phone)
    except Exception as e:  # noqa: BLE001
        await state.clear()
        await message.answer(f"❌ Kod yuborishda xatolik: {e}")
        return
    _login_flows[message.from_user.id] = flow
    await state.set_state(AdminState.tg_code)
    await message.answer(
        "📩 Telegramga kelgan kodni kiriting.\n\n"
        "⚠️ Xavfsizlik uchun kodni <b>bo'sh joylar bilan</b> yozing (masalan: "
        "<code>1 2 3 4 5</code>) — Telegram 'kodni chatga yozma' himoyasini chetlab o'tish uchun."
    )


@router.message(AdminState.tg_code)
async def tg_code_submit(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    flow = _login_flows.get(message.from_user.id)
    if not flow:
        await state.clear()
        await message.answer("❌ Sessiya topilmadi, qaytadan boshlang.")
        return
    code = message.text.strip().replace(" ", "")
    try:
        done = await flow.confirm_code(code)
    except Exception as e:  # noqa: BLE001
        await state.clear()
        _login_flows.pop(message.from_user.id, None)
        await message.answer(f"❌ Kod noto'g'ri yoki xatolik: {e}\nQaytadan urinib ko'ring.")
        return
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass

    if not done:
        # 2FA parol kerak
        await state.set_state(AdminState.tg_password)
        await message.answer("🔐 Akkauntingizda 2-bosqichli parol bor. Parolni kiriting:")
        return

    await tg_account.save_session(flow.session_string)
    _login_flows.pop(message.from_user.id, None)
    await state.clear()
    await message.answer("✅ Telegram akkaunt muvaffaqiyatli ulandi!")
    status = await fragment_service.get_account_status()
    await message.answer(await _tg_text(status), reply_markup=tg_account_menu(status),
                         disable_web_page_preview=True)


@router.message(AdminState.tg_password)
async def tg_password_submit(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    flow = _login_flows.get(message.from_user.id)
    if not flow:
        await state.clear()
        await message.answer("❌ Sessiya topilmadi, qaytadan boshlang.")
        return
    try:
        await flow.confirm_password(message.text.strip())
    except Exception as e:  # noqa: BLE001
        await message.answer(f"❌ Parol noto'g'ri: {e}\nQayta kiriting:")
        return
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
    await tg_account.save_session(flow.session_string)
    _login_flows.pop(message.from_user.id, None)
    await state.clear()
    await message.answer("✅ Telegram akkaunt (2FA bilan) muvaffaqiyatli ulandi!")
    status = await fragment_service.get_account_status()
    await message.answer(await _tg_text(status), reply_markup=tg_account_menu(status),
                         disable_web_page_preview=True)


# ---------- Session string joylash ----------
@router.callback_query(F.data == "tg:paste")
async def tg_paste_start(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return
    await state.set_state(AdminState.tg_session_paste)
    await call.message.answer(
        "📋 <code>python -m bot.login</code> orqali olgan <b>session string</b>'ni yuboring:"
    )
    await call.answer()


@router.message(AdminState.tg_session_paste)
async def tg_paste_save(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    session_str = message.text.strip()
    await state.clear()
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
    # tekshirib ko'ramiz
    info = await tg_account.check_session(session_str)
    if not info.get("ok"):
        await message.answer(f"❌ Session ishlamadi: {info.get('error')}\nQayta urinib ko'ring.")
        return
    await tg_account.save_session(session_str)
    await message.answer(
        f"✅ Session ulandi: @{info.get('username') or info.get('id')} ({info.get('name','')})"
    )
    status = await fragment_service.get_account_status()
    await message.answer(await _tg_text(status), reply_markup=tg_account_menu(status),
                         disable_web_page_preview=True)


# ---------- Tekshirish / uzish ----------
@router.callback_query(F.data == "tg:check")
async def tg_check(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return
    await call.answer("⏳ Tekshirilmoqda...")
    info = await tg_account.check_session()
    if info.get("ok"):
        await call.message.answer(
            f"✅ Ulanish ishlayapti.\n"
            f"👤 @{info.get('username') or info.get('id')} ({info.get('name','')})\n"
            f"📞 {info.get('phone','')}"
        )
    else:
        await call.message.answer(f"❌ {info.get('error')}")


@router.callback_query(F.data == "tg:clear")
async def tg_clear(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return
    await tg_account.clear_session()
    status = await fragment_service.get_account_status()
    await call.message.edit_text(await _tg_text(status), reply_markup=tg_account_menu(status),
                                 disable_web_page_preview=True)
    await call.answer("🗑 Telegram akkaunt uzildi.")


# ==================== ADMINLAR BOSHQARUVI ====================
async def _build_admins_list() -> list[dict]:
    """Barcha adminlar ro'yxati (env + DB) + owner belgisi bilan."""
    owner = await db.get_owner()
    if owner is None and settings.admin_id_list:
        owner = settings.admin_id_list[0]  # default owner
    env_ids = settings.admin_id_list
    db_ids = await db.get_db_admins()

    seen: dict[int, dict] = {}
    for uid in env_ids:
        seen[uid] = {"id": uid, "from_env": True, "is_owner": uid == owner}
    for uid in db_ids:
        if uid in seen:
            continue
        seen[uid] = {"id": uid, "from_env": False, "is_owner": uid == owner}
    if owner is not None and owner not in seen:
        seen[owner] = {"id": owner, "from_env": False, "is_owner": True}

    result = []
    for uid, info in seen.items():
        u = await db.get_user(uid)
        if u and u.username:
            label = f"@{u.username}"
        elif u and u.full_name:
            label = f"{u.full_name} ({uid})"
        else:
            label = str(uid)
        info["label"] = label
        result.append(info)
    # owner birinchi
    result.sort(key=lambda x: (not x["is_owner"], x["id"]))
    return result


@router.callback_query(F.data == "adm:admins")
async def adm_admins(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return
    await state.clear()
    from bot.keyboards.kb import admins_menu
    owner = await is_owner(call.from_user.id)
    admins = await _build_admins_list()
    text = (
        "👮 <b>Adminlar</b>\n\n"
        "👑 — bot egasi (owner)\n"
        "🔒 .env dagi adminlarni bu yerdan o'chirib bo'lmaydi.\n\n"
        + ("Admin qo'shish/o'chirish faqat egaga ruxsat etilgan." if owner
           else "Faqat bot egasi admin qo'sha/o'chira oladi.")
    )
    await call.message.edit_text(text, reply_markup=admins_menu(admins, owner))
    await call.answer()


@router.callback_query(F.data == "adm:addadmin")
async def adm_addadmin_start(call: CallbackQuery, state: FSMContext):
    if not await is_owner(call.from_user.id):
        await call.answer("Faqat bot egasi admin qo'sha oladi.", show_alert=True)
        return
    await state.set_state(AdminState.add_admin)
    await call.message.answer(
        "➕ Yangi admin Telegram ID sini kiriting.\n\n"
        "ℹ️ ID ni bilish uchun foydalanuvchi @userinfobot ga yozishi mumkin. "
        "U avval botni /start qilgan bo'lsa yaxshi."
    )
    await call.answer()


@router.message(AdminState.add_admin)
async def adm_addadmin_save(message: Message, state: FSMContext):
    if not await is_owner(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❌ ID son bo'lishi kerak. Qayta kiriting:")
        return
    uid = int(message.text.strip())
    await db.add_db_admin(uid)
    await state.clear()
    await message.answer(f"✅ {uid} admin qilib qo'shildi.")
    try:
        await message.bot.send_message(uid, "🎉 Siz bu botga admin qilib tayinlandingiz! /admin")
    except Exception:  # noqa: BLE001
        pass
    from bot.keyboards.kb import admins_menu
    admins = await _build_admins_list()
    await message.answer(
        "👮 <b>Adminlar</b>", reply_markup=admins_menu(admins, True)
    )


@router.callback_query(F.data.startswith("adm:deladmin:"))
async def adm_deladmin(call: CallbackQuery):
    if not await is_owner(call.from_user.id):
        await call.answer("Faqat bot egasi admin o'chira oladi.", show_alert=True)
        return
    uid = int(call.data.split(":")[2])
    owner = await db.get_owner() or (settings.admin_id_list[0] if settings.admin_id_list else None)
    if uid == owner:
        await call.answer("Egani o'chirib bo'lmaydi.", show_alert=True)
        return
    await db.remove_db_admin(uid)
    from bot.keyboards.kb import admins_menu
    admins = await _build_admins_list()
    await call.message.edit_text("👮 <b>Adminlar</b>", reply_markup=admins_menu(admins, True))
    await call.answer("🗑 Adminlikdan olindi.")
    try:
        await call.bot.send_message(uid, "ℹ️ Sizning admin huquqingiz bekor qilindi.")
    except Exception:  # noqa: BLE001
        pass


# ==================== EGALIKNI O'TKAZISH ====================
@router.callback_query(F.data == "adm:transfer")
async def adm_transfer_start(call: CallbackQuery, state: FSMContext):
    if not await is_owner(call.from_user.id):
        await call.answer("Faqat bot egasi egalikni o'tkaza oladi.", show_alert=True)
        return
    await state.set_state(AdminState.transfer_owner)
    await call.message.answer(
        "👑 <b>Egalikni o'tkazish</b>\n\n"
        "⚠️ DIQQAT: egalikni o'tkazsangiz, siz oddiy adminga aylanasiz. "
        "Yangi ega botni to'liq boshqaradi (admin qo'shish/o'chirish, akkaunt ulash).\n\n"
        "Yangi ega Telegram ID sini kiriting (bekor qilish uchun /cancel):"
    )
    await call.answer()


@router.message(AdminState.transfer_owner)
async def adm_transfer_confirm(message: Message, state: FSMContext):
    if not await is_owner(message.from_user.id):
        return
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return
    if not message.text.strip().isdigit():
        await message.answer("❌ ID son bo'lishi kerak. Qayta kiriting (yoki /cancel):")
        return
    new_owner = int(message.text.strip())
    old_owner = message.from_user.id
    await db.set_owner(new_owner)
    # yangi ega adminlar ro'yxatiga ham qo'shilsin
    await db.add_db_admin(new_owner)
    # eski ega admin bo'lib qoladi
    await db.add_db_admin(old_owner)
    await state.clear()
    await message.answer(
        f"👑 Egalik <code>{new_owner}</code> ga o'tkazildi.\n"
        f"Siz endi oddiy adminsiz."
    )
    try:
        await message.bot.send_message(
            new_owner,
            "👑 Tabriklaymiz! Siz bu botning yangi egasiga (owner) aylandingiz. /admin",
        )
    except Exception:  # noqa: BLE001
        pass
