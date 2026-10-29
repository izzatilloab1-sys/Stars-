"""FSM holatlari."""
from aiogram.fsm.state import State, StatesGroup


class BuyStars(StatesGroup):
    target = State()   # kimga (@username)
    amount = State()   # nechta Stars
    confirm = State()  # tasdiqlash / to'lov usuli


class PromoState(StatesGroup):
    code = State()


class AdminState(StatesGroup):
    broadcast = State()
    promo_code = State()
    promo_bonus = State()
    promo_uses = State()
    add_balance_user = State()
    add_balance_amount = State()
    # Akkaunt ulash
    set_seed = State()
    set_cookie_token = State()
    set_cookie_ssid = State()
    set_cookie_dt = State()
    set_cookie_ton = State()
    # Telegram akkaunt (telefon raqam orqali)
    tg_api_id = State()
    tg_api_hash = State()
    tg_phone = State()
    tg_code = State()
    tg_password = State()
    tg_session_paste = State()
    # Admin boshqaruvi
    add_admin = State()
    transfer_owner = State()
    # Narx / referal sozlamalari
    set_price = State()
    set_ref_stars = State()
    set_ref_threshold = State()
    # Stars ishlash (zadaniya) kanali qo'shish
    task_channel = State()
    task_reward = State()
    # Majburiy obuna kanali qo'shish
    req_channel = State()
    # Yechib olish (withdrawal) zayafka kanali
    set_withdraw_channel = State()
    # TON kursi (1 TON = ? so'm)
    set_ton_rate = State()
    # Referal oversight (foydalanuvchi kimlarni chaqirganini ko'rish)
    view_referrals = State()
