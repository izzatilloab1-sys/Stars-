"""Klaviaturalar (tugmalar)."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Asosiy menyu (reply-keyboard) tugmalarining barcha matnlari.
# MenuResetMiddleware shu to'plamdan foydalanib, menyu tugmasi bosilganda
# faol FSM holatini tozalaydi (bir oqim o'rtasida boshqa tugma ishlashi uchun).
MENU_BUTTONS: set[str] = {
    "⭐ Stars sotib olish",
    "💳 Balans to'ldirish",
    "👤 Profil",
    "👥 Referal",
    "📦 Buyurtmalarim",
    "🌟 Stars ishlash",
    "💸 Yechib olish",
    "🎁 Promokod",
    "ℹ️ Yordam",
    "🛠 Admin panel",
}


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="⭐ Stars sotib olish"))
    kb.row(
        KeyboardButton(text="💳 Balans to'ldirish"),
        KeyboardButton(text="👤 Profil"),
    )
    kb.row(
        KeyboardButton(text="👥 Referal"),
        KeyboardButton(text="📦 Buyurtmalarim"),
    )
    kb.row(
        KeyboardButton(text="🌟 Stars ishlash"),
        KeyboardButton(text="💸 Yechib olish"),
    )
    kb.row(
        KeyboardButton(text="🎁 Promokod"),
        KeyboardButton(text="ℹ️ Yordam"),
    )
    if is_admin:
        kb.row(KeyboardButton(text="🛠 Admin panel"))
    return kb.as_markup(resize_keyboard=True)


def topup_amount_kb() -> InlineKeyboardMarkup:
    """Balans to'ldirish uchun tayyor summalar."""
    kb = InlineKeyboardBuilder()
    for amount in (50_000, 100_000, 200_000, 500_000):
        kb.button(text=f"{amount:,} so'm", callback_data=f"topup:{amount}")
    kb.button(text="✏️ Boshqa summa", callback_data="topup:custom")
    kb.button(text="❌ Bekor qilish", callback_data="cancel")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def topup_payment_kb(amount: int) -> InlineKeyboardMarkup:
    """Balans to'ldirish uchun to'lov usullari (bonus balanssiz)."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💵 Karta (avto, so'm)", callback_data=f"tpay:card:{amount}"))
    kb.row(InlineKeyboardButton(text="💎 TON orqali", callback_data=f"tpay:ton:{amount}"))
    kb.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))
    return kb.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]]
    )


def star_packages_kb() -> InlineKeyboardMarkup:
    """Tayyor hadya paketlari (15/25/50 ...) + boshqa miqdor."""
    kb = InlineKeyboardBuilder()
    for pkg in (15, 25, 50, 100, 500, 1000):
        kb.button(text=f"🎁 {pkg} ⭐", callback_data=f"pkg:{pkg}")
    kb.button(text="✏️ Boshqa miqdor", callback_data="pkg:custom")
    kb.button(text="❌ Bekor qilish", callback_data="cancel")
    kb.adjust(3, 3, 1, 1)
    return kb.as_markup()


def withdraw_packages_kb() -> InlineKeyboardMarkup:
    """Stars yechib olish paketlari (minimal 15 ⭐)."""
    kb = InlineKeyboardBuilder()
    for pkg in (15, 25, 50):
        kb.button(text=f"{pkg} ⭐", callback_data=f"wd:req:{pkg}")
    kb.button(text="❌ Bekor qilish", callback_data="cancel")
    kb.adjust(3, 1)
    return kb.as_markup()


def withdraw_admin_kb(withdrawal_id: int) -> InlineKeyboardMarkup:
    """Zayafka tagidagi admin tugmalari: To'landi / Bekor qilish."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ To'landi", callback_data=f"wd:paid:{withdrawal_id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"wd:cancel:{withdrawal_id}"),
    )
    return kb.as_markup()


def payment_methods_kb(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💳 Click (so'm)", callback_data=f"pay:click:{order_id}"))
    kb.row(InlineKeyboardButton(text="💳 Payme (so'm)", callback_data=f"pay:payme:{order_id}"))
    kb.row(InlineKeyboardButton(text="💎 TON orqali", callback_data=f"pay:ton:{order_id}"))
    kb.row(InlineKeyboardButton(text="💰 Bonus balansdan", callback_data=f"pay:balance:{order_id}"))
    kb.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))
    return kb.as_markup()


def check_payment_kb(order_id: int, pay_url: str | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if pay_url:
        kb.row(InlineKeyboardButton(text="💳 To'lash", url=pay_url))
    kb.row(InlineKeyboardButton(text="✅ To'ladim / Tekshirish", callback_data=f"check:{order_id}"))
    kb.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))
    return kb.as_markup()


def confirm_order_kb(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm:{order_id}"))
    kb.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))
    return kb.as_markup()


# ---------- Admin ----------
def admin_menu(is_owner: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"))
    kb.row(InlineKeyboardButton(text="🔗 Akkaunt ulash", callback_data="adm:account"))
    kb.row(InlineKeyboardButton(text="🎁 Promokod yaratish", callback_data="adm:promo"))
    kb.row(InlineKeyboardButton(text="💰 Balans qo'shish", callback_data="adm:addbal"))
    kb.row(InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="adm:broadcast"))
    kb.row(InlineKeyboardButton(text="🌟 Stars ishlash (zadaniya)", callback_data="adm:tasks"))
    kb.row(InlineKeyboardButton(text="📢 Majburiy obuna", callback_data="adm:subs"))
    kb.row(InlineKeyboardButton(text="👥 Referallarni ko'rish", callback_data="adm:refs"))
    kb.row(InlineKeyboardButton(text="⚙️ Narx va referal sozlamalari", callback_data="adm:settings"))
    kb.row(InlineKeyboardButton(text="👮 Adminlar", callback_data="adm:admins"))
    if is_owner:
        kb.row(InlineKeyboardButton(text="👑 Egalikni o'tkazish", callback_data="adm:transfer"))
    return kb.as_markup()


def settings_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💰 1 Star narxini o'zgartirish", callback_data="set:price"))
    kb.row(InlineKeyboardButton(text="👥 Referal Stars sonini o'zgartirish", callback_data="set:refstars"))
    kb.row(InlineKeyboardButton(text="🎯 Referal zadaniya chegarasi", callback_data="set:refthreshold"))
    kb.row(InlineKeyboardButton(text="💎 TON kursi (1 TON = ? so'm)", callback_data="set:tonrate"))
    kb.row(InlineKeyboardButton(text="💵 Karta raqami (avto to'lov)", callback_data="set:card"))
    kb.row(InlineKeyboardButton(text="🏦 Bank yuboruvchilar (avto)", callback_data="set:banksenders"))
    kb.row(InlineKeyboardButton(text="💸 Yechib olish kanali", callback_data="adm:withdrawch"))
    kb.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="adm:back"))
    return kb.as_markup()


# ---------- Stars ishlash (zadaniya) ----------
def admin_tasks_menu(tasks: list) -> InlineKeyboardMarkup:
    """Admin uchun zadaniya (reklama kanali) ro'yxati + toggle/o'chirish."""
    kb = InlineKeyboardBuilder()
    for t in tasks:
        label = t.title or t.channel_id
        kb.row(InlineKeyboardButton(
            text=f"🌟 {label} — {t.reward_stars} ⭐",
            callback_data="noop",
        ))
        kb.row(
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"task:del:{t.id}"),
        )
    kb.row(InlineKeyboardButton(text="➕ Zadaniya qo'shish", callback_data="task:add"))
    kb.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="adm:back"))
    return kb.as_markup()


def tasks_list_kb(tasks: list) -> InlineKeyboardMarkup:
    """Foydalanuvchiga ko'rsatiladigan zadaniyalar: obuna + Tekshirish tugmalari."""
    kb = InlineKeyboardBuilder()
    for t in tasks:
        label = t.title or t.channel_id
        url = t.invite_link
        if not url and isinstance(t.channel_id, str) and t.channel_id.startswith("@"):
            url = f"https://t.me/{t.channel_id[1:]}"
        if url:
            kb.row(InlineKeyboardButton(text=f"➕ Obuna bo'lish: {label}", url=url))
        kb.row(InlineKeyboardButton(
            text=f"✅ Tekshirish ({t.reward_stars} ⭐)",
            callback_data=f"task:check:{t.id}",
        ))
    return kb.as_markup()


# ---------- Majburiy obuna (forced subscription) ----------
def admin_subs_menu(channels: list) -> InlineKeyboardMarkup:
    """Admin uchun majburiy obuna kanallari ro'yxati + toggle/o'chirish."""
    kb = InlineKeyboardBuilder()
    for ch in channels:
        label = ch.title or ch.channel_id
        mark = "🟢" if ch.is_active else "🔴"
        kb.row(InlineKeyboardButton(text=f"{mark} {label}", callback_data="noop"))
        kb.row(
            InlineKeyboardButton(
                text="⏸ O'chirish" if ch.is_active else "▶️ Yoqish",
                callback_data=f"sub:toggle:{ch.id}",
            ),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"sub:del:{ch.id}"),
        )
    kb.row(InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="sub:add"))
    kb.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="adm:back"))
    return kb.as_markup()


def subscribe_gate_kb(channels: list) -> InlineKeyboardMarkup:
    """Foydalanuvchiga: har bir majburiy kanalga obuna tugmasi + Tekshirish."""
    kb = InlineKeyboardBuilder()
    for ch in channels:
        label = ch.title or ch.channel_id
        url = ch.invite_link
        if not url and isinstance(ch.channel_id, str) and ch.channel_id.startswith("@"):
            url = f"https://t.me/{ch.channel_id[1:]}"
        if url:
            kb.row(InlineKeyboardButton(text=f"📢 {label}", url=url))
    kb.row(InlineKeyboardButton(text="✅ Tekshirish", callback_data="sub:check"))
    return kb.as_markup()


def admins_menu(admins: list[dict], is_owner: bool) -> InlineKeyboardMarkup:
    """Adminlar ro'yxati. Har biri yonida o'chirish tugmasi (faqat owner uchun)."""
    kb = InlineKeyboardBuilder()
    for a in admins:
        label = f"{'👑 ' if a['is_owner'] else ''}{a['label']}"
        if is_owner and not a["is_owner"] and not a["from_env"]:
            kb.row(
                InlineKeyboardButton(text=label, callback_data="noop"),
                InlineKeyboardButton(text="🗑", callback_data=f"adm:deladmin:{a['id']}"),
            )
        else:
            kb.row(InlineKeyboardButton(text=label, callback_data="noop"))
    if is_owner:
        kb.row(InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="adm:addadmin"))
    kb.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="adm:back"))
    return kb.as_markup()


def account_menu(status: dict) -> InlineKeyboardMarkup:
    """Akkaunt ulash menyusi — holatga qarab belgilar bilan."""
    seed_mark = "✅" if status.get("seed_set") else "❌"
    cookie_mark = "✅" if status.get("cookie_set") else "❌"
    mode = status.get("mode", "manual")
    kb = InlineKeyboardBuilder()
    tg_mark = "✅" if status.get("tg_set") else "❌"
    kb.row(InlineKeyboardButton(text=f"🔑 Hamyon seed (Tonkeeper) {seed_mark}", callback_data="acc:seed"))
    kb.row(InlineKeyboardButton(text=f"📱 Telegram akkaunt (raqam) {tg_mark}", callback_data="acc:tg"))
    kb.row(InlineKeyboardButton(text=f"🍪 Fragment cookie {cookie_mark}", callback_data="acc:cookie"))
    mode_label = "fragment (avto)" if mode == "fragment" else "manual (qo'lda)"
    kb.row(InlineKeyboardButton(text=f"⚙️ Rejim: {mode_label}", callback_data="acc:mode"))
    wv = status.get("wallet_version", "v5r1")
    wv_label = "W5 (v5r1)" if wv == "v5r1" else "v4r2"
    kb.row(InlineKeyboardButton(text=f"🪙 Hamyon versiyasi: {wv_label}", callback_data="acc:wallet"))
    kb.row(InlineKeyboardButton(text="💎 Balansni tekshirish", callback_data="acc:balance"))
    kb.row(InlineKeyboardButton(text="🗑 Akkauntni uzish", callback_data="acc:clear"))
    kb.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="adm:back"))
    return kb.as_markup()


def tg_account_menu(status: dict) -> InlineKeyboardMarkup:
    """Telegram akkaunt ulash menyusi."""
    api_mark = "✅" if status.get("tg_api_set") else "❌"
    tg_mark = "✅" if status.get("tg_set") else "❌"
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"🔧 api_id / api_hash {api_mark}", callback_data="tg:api"))
    kb.row(InlineKeyboardButton(text="📞 Raqam orqali ulash", callback_data="tg:phone"))
    kb.row(InlineKeyboardButton(text="📋 Session string joylash", callback_data="tg:paste"))
    if status.get("tg_set"):
        kb.row(InlineKeyboardButton(text="🔍 Ulanishni tekshirish", callback_data="tg:check"))
        kb.row(InlineKeyboardButton(text="🗑 Akkauntni uzish", callback_data="tg:clear"))
    kb.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="adm:account"))
    return kb.as_markup()


def admin_delivery_kb(order_id: int) -> InlineKeyboardMarkup:
    """Manual rejimda admin yetkazishni tasdiqlaydi."""
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Yetkazdim", callback_data=f"deliver:done:{order_id}"))
    kb.row(InlineKeyboardButton(text="↩️ Pulni qaytarish", callback_data=f"deliver:refund:{order_id}"))
    return kb.as_markup()
