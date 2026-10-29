"""Klaviaturalar (tugmalar)."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="⭐ Stars sotib olish"))
    kb.row(
        KeyboardButton(text="👤 Profil"),
        KeyboardButton(text="👥 Referal"),
    )
    kb.row(
        KeyboardButton(text="🎁 Promokod"),
        KeyboardButton(text="📦 Buyurtmalarim"),
    )
    kb.row(KeyboardButton(text="ℹ️ Yordam"))
    return kb.as_markup(resize_keyboard=True)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]]
    )


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
def admin_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"))
    kb.row(InlineKeyboardButton(text="🔗 Akkaunt ulash", callback_data="adm:account"))
    kb.row(InlineKeyboardButton(text="🎁 Promokod yaratish", callback_data="adm:promo"))
    kb.row(InlineKeyboardButton(text="💰 Balans qo'shish", callback_data="adm:addbal"))
    kb.row(InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="adm:broadcast"))
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
