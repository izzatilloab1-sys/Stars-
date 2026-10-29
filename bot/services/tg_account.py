"""
Telegram akkauntni telefon raqam orqali ulash (Telethon, MTProto).

Ikki rejimda ishlatiladi:
  A) Bot ichida (admin panel): raqam yuboriladi -> SMS kod keladi -> kod kiritiladi
     -> (kerak bo'lsa 2FA parol) -> session string yaratiladi va DB'ga saqlanadi.
  B) Alohida skript (python -m bot.login): terminalda interaktiv login.

Session string — StringSession formatida. U sizning Telegram akkauntingizga
to'liq kirish beradi, shuning uchun MAXFIY (hamyon seed kabi) saqlanadi.

⚠️ api_id / api_hash my.telegram.org -> API development tools dan olinadi.
"""
from __future__ import annotations

import logging

from bot.config import settings

logger = logging.getLogger(__name__)


async def _creds() -> tuple[int, str]:
    """api_id/api_hash ni avval DB'dan (admin panel), bo'lmasa .env'dan oladi."""
    from bot.database import db
    api_id = await db.get_setting("tg_api_id", str(settings.tg_api_id or ""))
    api_hash = await db.get_setting("tg_api_hash", settings.tg_api_hash)
    return (int(api_id) if api_id and api_id.isdigit() else 0), api_hash


async def get_session() -> str:
    """Saqlangan session string (DB -> .env)."""
    from bot.database import db
    val = await db.get_setting("tg_session", "")
    return val if val else settings.tg_session


async def save_session(session_str: str) -> None:
    from bot.database import db
    await db.set_setting("tg_session", session_str)


async def clear_session() -> None:
    from bot.database import db
    await db.set_setting("tg_session", "")


class LoginFlow:
    """
    Telefon raqam orqali login oqimini boshqaradi (bot ichida, bosqichma-bosqich).

    Foydalanish:
        flow = LoginFlow()
        await flow.start(phone)          # SMS kod yuboradi
        await flow.confirm_code(code)    # kodni tasdiqlaydi
        # agar 2FA bo'lsa:
        await flow.confirm_password(pw)
        session_str = flow.session_string
    """

    def __init__(self):
        self.client = None
        self.phone = None
        self.phone_code_hash = None
        self.session_string = None

    async def _get_client(self):
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        api_id, api_hash = await _creds()
        if not api_id or not api_hash:
            raise ValueError("api_id / api_hash sozlanmagan. Admin panel yoki .env orqali kiriting.")
        if self.client is None:
            self.client = TelegramClient(StringSession(), api_id, api_hash)
            await self.client.connect()
        return self.client

    async def start(self, phone: str) -> None:
        """Raqamga SMS/telegram kod yuboradi."""
        client = await self._get_client()
        self.phone = phone
        sent = await client.send_code_request(phone)
        self.phone_code_hash = sent.phone_code_hash

    async def confirm_code(self, code: str) -> bool:
        """Kodni tasdiqlaydi. True -> login tugadi; False -> 2FA parol kerak."""
        from telethon.errors import SessionPasswordNeededError
        from telethon.sessions import StringSession

        client = self.client
        try:
            await client.sign_in(
                phone=self.phone, code=code, phone_code_hash=self.phone_code_hash
            )
        except SessionPasswordNeededError:
            return False  # 2FA parol kerak
        self.session_string = StringSession.save(client.session)
        await client.disconnect()
        return True

    async def confirm_password(self, password: str) -> None:
        """2FA parolni tasdiqlaydi va session'ni yakunlaydi."""
        from telethon.sessions import StringSession
        client = self.client
        await client.sign_in(password=password)
        self.session_string = StringSession.save(client.session)
        await client.disconnect()

    async def cancel(self) -> None:
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:  # noqa: BLE001
                pass


async def check_session(session_str: str | None = None) -> dict:
    """Saqlangan session ishlayotganini tekshiradi. Akkaunt ma'lumotini qaytaradi."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    if session_str is None:
        session_str = await get_session()
    if not session_str:
        return {"ok": False, "error": "Session ulanmagan."}

    api_id, api_hash = await _creds()
    if not api_id or not api_hash:
        return {"ok": False, "error": "api_id / api_hash sozlanmagan."}

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return {"ok": False, "error": "Session eskirgan yoki bekor qilingan."}
        me = await client.get_me()
        return {
            "ok": True,
            "id": me.id,
            "username": me.username,
            "phone": me.phone,
            "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    finally:
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass
