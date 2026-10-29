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
from bot.middlewares import BanMiddleware

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

    # Middleware (banlanganlarni to'xtatadi)
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

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
