"""
Telegram akkauntni ulash uchun ALOHIDA interaktiv skript (Usul B).

Terminalda ishga tushiring:
    python -m bot.login

Bu skript:
  1. api_id / api_hash so'raydi (yoki .env dan oladi)
  2. telefon raqamingizni so'raydi -> Telegram kod yuboradi
  3. kodni (va kerak bo'lsa 2FA parolni) so'raydi
  4. SESSION STRING chiqaradi

Chiqqan session string'ni:
  - .env ga TG_SESSION=... deb yozasiz, YOKI
  - botda /admin -> 🔗 Akkaunt ulash -> 📱 Session string joylash orqali kiritasiz.

⚠️ Session string MAXFIY — uni hech kimga bermang. Terminal tarixidan ham o'chiring.
"""
from __future__ import annotations

import asyncio

from bot.config import settings


async def main() -> None:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    print("=== Telegram akkauntni ulash (session string olish) ===\n")

    api_id = settings.tg_api_id
    api_hash = settings.tg_api_hash
    if not api_id:
        api_id = int(input("api_id (my.telegram.org dan): ").strip())
    if not api_hash:
        api_hash = input("api_hash (my.telegram.org dan): ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()  # interaktiv: telefon, kod, 2FA parolni o'zi so'raydi

    me = await client.get_me()
    session_string = StringSession.save(client.session)

    print("\n✅ Muvaffaqiyatli ulandi!")
    print(f"   Akkaunt: {me.first_name} (@{me.username}) | id={me.id}\n")
    print("=" * 60)
    print("SESSION STRING (buni .env ga TG_SESSION= ga qo'ying yoki admin panelga):\n")
    print(session_string)
    print("=" * 60)
    print("\n⚠️  Bu string MAXFIY. Hech kimga bermang!")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
