"""Bot kirish nuqtasi."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.database import db
from bot.handlers import admin, buy, payment, topup, user
from bot.middlewares import BanMiddleware, MenuResetMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await db.init_db()
    logger.info("Ma'lumotlar bazasi tayyor.")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Middleware
    # MenuResetMiddleware — outer: FSM handler filtri tekshirilishidan OLDIN ishlaydi,
    # shunda menyu tugmasi bosilganda eski holat tozalanadi.
    dp.message.outer_middleware(MenuResetMiddleware())
    # BanMiddleware — banlanganlarni to'xtatadi
    dp.message.middleware(BanMiddleware())
    dp.callback_query.middleware(BanMiddleware())

    # Routerlar
    dp.include_router(admin.router)
    dp.include_router(buy.router)
    dp.include_router(topup.router)
    dp.include_router(payment.router)
    dp.include_router(user.router)  # user oxirida (umumiy matnli tugmalar)

    me = await bot.get_me()
    logger.info("Bot ishga tushdi: @%s", me.username)

    # Avto karta to'lovi listener'ini fon vazifasi sifatida ishga tushiramiz.
    # (Telegram akkaunt session'i ulanmagan bo'lsa, u jimgina chiqadi.)
    from bot.services.payment_listener import start_payment_listener
    listener_task = asyncio.create_task(start_payment_listener(bot))
    cleanup_task = asyncio.create_task(_expire_card_topups_loop())

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        listener_task.cancel()
        cleanup_task.cancel()
        await bot.session.close()


async def _expire_card_topups_loop() -> None:
    """Muddati o'tgan karta to'lovlarini davriy tozalaydi (har 60 soniya)."""
    while True:
        try:
            await asyncio.sleep(60)
            n = await db.expire_old_card_topups()
            if n:
                logger.info("Muddati o'tgan %s ta karta to'lovi tozalandi.", n)
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001
            logger.exception("Karta to'lovlarini tozalashda xatolik")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
