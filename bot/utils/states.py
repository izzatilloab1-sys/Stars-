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
