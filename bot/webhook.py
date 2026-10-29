"""
To'lov provayderlari (Payme, Click) uchun webhook (callback) serveri.

Bu alohida aiohttp server bo'lib, Payme/Click serverlaridan kelgan so'rovlarni
qabul qiladi, imzo/avtorizatsiyani tekshiradi, buyurtmani PAID qiladi va
Stars yetkazishni ishga tushiradi.

Ishga tushirish:
    python -m bot.webhook

Prodakshnda bu serverni domenga (HTTPS) ulang va Payme/Click kabinetida
callback URL sifatida ko'rsating:
    Payme:  https://sizning-domen.uz/payme
    Click:  https://sizning-domen.uz/click
"""
from __future__ import annotations

import base64
import hashlib
import logging
import time

from aiohttp import web
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.database import db
from bot.database.models import OrderStatus
from bot.handlers.payment import _deliver_and_finish

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Payme JSON-RPC xatolik kodlari
PAYME_ERR_METHOD = -32601
PAYME_ERR_AUTH = -32504
PAYME_ERR_ORDER = -31050
PAYME_ERR_AMOUNT = -31001
PAYME_ERR_TXN = -31003

bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)


# =================== PAYME ===================
def _check_payme_auth(request: web.Request) -> bool:
    """Payme Basic auth: login 'Paycom', parol = PAYME_KEY."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth[6:]).decode()
        _, password = decoded.split(":", 1)
    except Exception:  # noqa: BLE001
        return False
    return password == settings.payme_key


def _payme_error(req_id, code: int, message: str) -> web.Response:
    return web.json_response(
        {"error": {"code": code, "message": message}, "id": req_id}
    )


async def payme_handler(request: web.Request) -> web.Response:
    if not _check_payme_auth(request):
        return _payme_error(None, PAYME_ERR_AUTH, "Avtorizatsiya xato")

    data = await request.json()
    method = data.get("method")
    params = data.get("params", {})
    req_id = data.get("id")
    logger.info("Payme: %s %s", method, params)

    # --- CheckPerformTransaction ---
    if method == "CheckPerformTransaction":
        order_id = int(params.get("account", {}).get("order_id", 0))
        amount = int(params.get("amount", 0)) // 100  # tiyin -> so'm
        order = await db.get_order(order_id)
        if not order:
            return _payme_error(req_id, PAYME_ERR_ORDER, "Buyurtma topilmadi")
        if order.amount != amount:
            return _payme_error(req_id, PAYME_ERR_AMOUNT, "Summa noto'g'ri")
        return web.json_response({"result": {"allow": True}, "id": req_id})

    # --- CreateTransaction ---
    if method == "CreateTransaction":
        order_id = int(params.get("account", {}).get("order_id", 0))
        txn_id = params.get("id")
        order = await db.get_order(order_id)
        if not order:
            return _payme_error(req_id, PAYME_ERR_ORDER, "Buyurtma topilmadi")
        await db.set_order_field(order_id, payment_id=txn_id, payment_method="payme")
        return web.json_response({
            "result": {
                "create_time": int(time.time() * 1000),
                "transaction": str(order_id),
                "state": 1,
            },
            "id": req_id,
        })

    # --- PerformTransaction (to'lov yakunlandi) ---
    if method == "PerformTransaction":
        txn_id = params.get("id")
        order = await _find_order_by_payment_id(txn_id)
        if not order:
            return _payme_error(req_id, PAYME_ERR_TXN, "Tranzaksiya topilmadi")
        if await db.mark_paid_if_pending(order.id, txn_id):
            # Stars yetkazishni ishga tushiramiz (faqat birinchi marta)
            await _deliver_and_finish(bot, order.id)
        return web.json_response({
            "result": {
                "perform_time": int(time.time() * 1000),
                "transaction": str(order.id),
                "state": 2,
            },
            "id": req_id,
        })

    # --- CancelTransaction ---
    if method == "CancelTransaction":
        txn_id = params.get("id")
        order = await _find_order_by_payment_id(txn_id)
        if order:
            await db.set_order_status(order.id, OrderStatus.REFUNDED)
        return web.json_response({
            "result": {
                "cancel_time": int(time.time() * 1000),
                "transaction": str(order.id if order else 0),
                "state": -1,
            },
            "id": req_id,
        })

    # --- CheckTransaction ---
    if method == "CheckTransaction":
        txn_id = params.get("id")
        order = await _find_order_by_payment_id(txn_id)
        if not order:
            return _payme_error(req_id, PAYME_ERR_TXN, "Tranzaksiya topilmadi")
        state = 2 if order.status in (OrderStatus.PAID, OrderStatus.DELIVERING, OrderStatus.DONE) else 1
        return web.json_response({
            "result": {"state": state, "transaction": str(order.id)},
            "id": req_id,
        })

    return _payme_error(req_id, PAYME_ERR_METHOD, "Metod topilmadi")


async def _find_order_by_payment_id(payment_id: str):
    from sqlalchemy import select
    from bot.database.models import Order
    async with db.Session() as s:
        res = await s.execute(select(Order).where(Order.payment_id == str(payment_id)))
        return res.scalar_one_or_none()


# =================== CLICK ===================
async def click_handler(request: web.Request) -> web.Response:
    """Click Prepare/Complete callback'lari."""
    data = await request.post()
    action = data.get("action")  # 0 = Prepare, 1 = Complete
    order_id = int(data.get("merchant_trans_id", 0) or 0)
    amount = int(float(data.get("amount", 0) or 0))
    sign_string = data.get("sign_string", "")
    sign_time = data.get("sign_time", "")
    click_trans_id = data.get("click_trans_id", "")

    # imzo tekshiruvi
    expected = _click_sign(data, action)
    if sign_string != expected:
        return web.json_response({"error": -1, "error_note": "Imzo noto'g'ri"})

    order = await db.get_order(order_id)
    if not order:
        return web.json_response({"error": -5, "error_note": "Buyurtma topilmadi"})
    if order.amount != amount:
        return web.json_response({"error": -2, "error_note": "Summa noto'g'ri"})

    if action == "0":  # Prepare
        await db.set_order_field(order_id, payment_id=str(click_trans_id), payment_method="click")
        return web.json_response({
            "error": 0, "error_note": "Success",
            "click_trans_id": click_trans_id,
            "merchant_trans_id": str(order_id),
            "merchant_prepare_id": str(order_id),
        })

    if action == "1":  # Complete
        if await db.mark_paid_if_pending(order_id, str(click_trans_id)):
            await _deliver_and_finish(bot, order_id)
        return web.json_response({
            "error": 0, "error_note": "Success",
            "click_trans_id": click_trans_id,
            "merchant_trans_id": str(order_id),
            "merchant_confirm_id": str(order_id),
        })

    return web.json_response({"error": -3, "error_note": "Noma'lum action"})


def _click_sign(data, action) -> str:
    """Click imzosi (MD5)."""
    raw = (
        f"{data.get('click_trans_id','')}"
        f"{data.get('service_id','')}"
        f"{settings.click_secret_key}"
        f"{data.get('merchant_trans_id','')}"
        f"{data.get('merchant_prepare_id','') if action == '1' else ''}"
        f"{data.get('amount','')}"
        f"{action}"
        f"{data.get('sign_time','')}"
    )
    return hashlib.md5(raw.encode()).hexdigest()


# =================== Server ===================
def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/payme", payme_handler)
    app.router.add_post("/click", click_handler)
    app.router.add_get("/health", lambda r: web.json_response({"status": "ok"}))
    return app


async def _on_startup(app):
    await db.init_db()
    logger.info("Webhook server tayyor.")


def main():
    app = create_app()
    app.on_startup.append(_on_startup)
    port = int(settings.webhook_port)
    logger.info("Webhook server %s portda ishga tushmoqda...", port)
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
