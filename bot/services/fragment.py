"""
Fragment orqali Stars yetkazish moduli.

Fragment'ning RASMIY ommaviy API'si yo'q. Avtomatik sotib olish uchun ikkita
narsa kerak (ikkalasi ham SIZNING shaxsiy ma'lumotlaringiz):

  1. Fragment cookie'lari  — fragment.com'ga Telegram orqali login qilingach,
     brauzer cookie'laridan olinadi:
        stel_token, stel_ssid, stel_dt, stel_ton_token
  2. TON hamyon seed (12/24 so'z) — Stars uchun to'lov shu hamyondan yechiladi.
     Hamyonda yetarli TON bo'lishi kerak.

Rejimlar (FRAGMENT_MODE):
  - manual   -> avtomatik yetkazilmaydi; adminga xabar ketadi, admin qo'lda
                yuborib "Yetkazdim" bosadi. (kalit talab qilmaydi)
  - fragment -> cookie + seed orqali Fragment'dan AVTOMATIK sotib oladi.

Bu modul bir nechta ommabop unofficial kutubxonani qo'llab-quvvatlaydi
(fragment-api, pyfragment va h.k.) — qaysi biri o'rnatilgan bo'lsa, o'shani
ishlatadi. Interfeyslar biroz farq qilgani uchun adapterlar yozilgan.

⚠️ XAVFSIZLIK: cookie va seed sizning akkaunt/hamyoningizga to'liq kirishdir.
Ularni faqat o'zingiz ishonadigan serverda .env'da saqlang, git'ga qo'ymang.
"""
from __future__ import annotations

import asyncio
import logging

from bot.config import settings

logger = logging.getLogger(__name__)


class DeliveryResult:
    def __init__(self, ok: bool, message: str, tx_id: str | None = None):
        self.ok = ok
        self.message = message
        self.tx_id = tx_id


async def _cfg(key: str, env_default: str) -> str:
    """Sozlamani avval DB'dan (admin panel), bo'sh bo'lsa .env'dan oladi."""
    from bot.database import db
    val = await db.get_setting(key, "")
    return val if val else env_default


async def get_fragment_mode() -> str:
    return await _cfg("fragment_mode", settings.fragment_mode)


async def get_wallet_seed() -> str:
    return await _cfg("ton_wallet_mnemonic", settings.ton_wallet_mnemonic)


async def _fragment_cookies() -> dict:
    return {
        "stel_token": await _cfg("fragment_stel_token", settings.fragment_stel_token),
        "stel_ssid": await _cfg("fragment_stel_ssid", settings.fragment_stel_ssid),
        "stel_dt": await _cfg("fragment_stel_dt", settings.fragment_stel_dt),
        "stel_ton_token": await _cfg("fragment_stel_ton_token", settings.fragment_stel_ton_token),
    }


async def deliver_stars(target_username: str, stars: int) -> DeliveryResult:
    """Berilgan username'ga Stars yetkazadi."""
    username = target_username.lstrip("@")
    mode = await get_fragment_mode()

    if mode == "manual":
        logger.info("Manual rejim: @%s uchun %s Stars admin tomonidan yuboriladi", username, stars)
        return DeliveryResult(ok=False, message="manual rejim — admin tomonidan yetkaziladi")

    if mode == "fragment":
        return await _deliver_via_fragment(username, stars)

    return DeliveryResult(ok=False, message=f"Noma'lum FRAGMENT_MODE: {mode}")


async def _deliver_via_fragment(username: str, stars: int) -> DeliveryResult:
    """Fragment cookie + TON seed orqali avtomatik Stars sotib oladi.

    Mavjud kutubxonalardan birini sinab ko'radi. Buy xatosiz o'tsa -> ok=True.
    """
    seed = (await get_wallet_seed()).strip()
    cookies = await _fragment_cookies()

    # Zarur sozlamalar borligini tekshiramiz
    if not seed:
        return DeliveryResult(ok=False, message="Hamyon seed sozlanmagan (admin panel yoki .env).")
    if not cookies.get("stel_token"):
        return DeliveryResult(ok=False, message="Fragment cookie'lari sozlanmagan (admin panel yoki .env).")

    # --- Adapter 1: fragment-api (S1qwy/fragment-api-py oilasidagi sinxron klient) ---
    try:
        return await _try_fragment_api(username, stars, seed, cookies)
    except ImportError:
        logger.info("fragment-api topilmadi, keyingi adapterni sinayman.")
    except Exception as e:  # noqa: BLE001
        logger.exception("fragment-api orqali xatolik")
        return DeliveryResult(ok=False, message=f"Fragment xatolik: {e}")

    # --- Adapter 2: pyfragment (bohd4nx) ---
    try:
        return await _try_pyfragment(username, stars, seed, cookies)
    except ImportError:
        logger.info("pyfragment topilmadi.")
    except Exception as e:  # noqa: BLE001
        logger.exception("pyfragment orqali xatolik")
        return DeliveryResult(ok=False, message=f"Fragment xatolik: {e}")

    return DeliveryResult(
        ok=False,
        message=(
            "Fragment kutubxonasi o'rnatilmagan. "
            "`pip install fragment-api` yoki `pip install pyfragment` qiling."
        ),
    )


async def _try_fragment_api(username: str, stars: int, seed: str, cookies: dict) -> DeliveryResult:
    """fragment-api oilasidagi klient interfeysi (sinxron -> thread'da).

    Odatiy interfeys:
        from fragment_api import FragmentAPI
        api = FragmentAPI(cookies=..., seed=...)
        res = api.buy_stars(username=..., amount=...)
    Kutubxona versiyasiga qarab nomlar farq qilishi mumkin — shu sabab
    import va chaqiruv himoyalangan.
    """
    def _run() -> DeliveryResult:
        try:
            from fragment_api import FragmentAPI  # type: ignore
        except ImportError:
            from fragment_api_py import FragmentAPI  # type: ignore  # muqobil paket nomi

        api = FragmentAPI(cookies=cookies, seed=seed.split())
        # payment_method: hamyondan TON yoki USDT yechiladi
        pay = settings.fragment_pay_currency.lower()  # "ton" | "usdt"
        try:
            res = api.buy_stars(username=username, amount=stars, payment_method=pay)
        except TypeError:
            # eski versiyalarda payment_method parametri bo'lmasligi mumkin
            res = api.buy_stars(username=username, amount=stars)
        # res formati kutubxonaga bog'liq: dict yoki obyekt bo'lishi mumkin
        tx = None
        ok = True
        if isinstance(res, dict):
            ok = bool(res.get("ok", True))
            tx = res.get("tx_hash") or res.get("hash") or res.get("transaction")
        else:
            tx = getattr(res, "tx_hash", None) or getattr(res, "hash", None)
            ok = getattr(res, "ok", True)
        return DeliveryResult(ok=ok, message="Fragment orqali yuborildi" if ok else "Fragment rad etdi", tx_id=tx)

    return await asyncio.to_thread(_run)


async def _try_pyfragment(username: str, stars: int, seed: str, cookies: dict) -> DeliveryResult:
    """pyfragment (bohd4nx) — async klient.

    Odatiy interfeys:
        from pyfragment import Fragment
        async with Fragment(cookies=..., mnemonic=...) as f:
            res = await f.buy_stars(username, stars)
    """
    from pyfragment import Fragment  # type: ignore

    async with Fragment(cookies=cookies, mnemonic=seed.split()) as f:
        res = await f.buy_stars(username, stars)
        tx = None
        ok = True
        if isinstance(res, dict):
            ok = bool(res.get("ok", True))
            tx = res.get("tx_hash") or res.get("hash")
        else:
            tx = getattr(res, "tx_hash", None) or getattr(res, "hash", None)
            ok = getattr(res, "ok", True)
        return DeliveryResult(ok=ok, message="Fragment orqali yuborildi" if ok else "Fragment rad etdi", tx_id=tx)


# ---------- Admin panel uchun: ulanishni tekshirish ----------
async def get_account_status() -> dict:
    """Ulangan akkaunt holatini qaytaradi (admin panel uchun)."""
    seed = (await get_wallet_seed()).strip()
    cookies = await _fragment_cookies()
    mode = await get_fragment_mode()
    seed_words = len(seed.split()) if seed else 0
    # Telegram akkaunt holati
    from bot.database import db
    tg_session = await db.get_setting("tg_session", settings.tg_session)
    tg_api_id = await db.get_setting("tg_api_id", str(settings.tg_api_id or ""))
    tg_api_hash = await db.get_setting("tg_api_hash", settings.tg_api_hash)
    return {
        "mode": mode,
        "seed_set": bool(seed),
        "seed_words": seed_words,
        "cookie_set": bool(cookies.get("stel_token")),
        "wallet_address": await get_wallet_address(seed) if seed else None,
        "tg_set": bool(tg_session),
        "tg_api_set": bool(tg_api_id and tg_api_id != "0" and tg_api_hash),
    }


async def get_wallet_address(seed: str | None = None) -> str | None:
    """Seed'dan hamyon manzilini hisoblaydi (ko'rsatish uchun)."""
    if seed is None:
        seed = (await get_wallet_seed()).strip()
    if not seed:
        return None
    try:
        import asyncio

        def _run() -> str | None:
            try:
                from tonutils.client import TonapiClient  # type: ignore
                from tonutils.wallet import WalletV4R2  # type: ignore
                client = TonapiClient(api_key=settings.ton_api_key or "")
                wallet, _, _, _ = WalletV4R2.from_mnemonic(client, seed.split())
                return wallet.address.to_str()
            except Exception:  # noqa: BLE001
                return None

        return await asyncio.to_thread(_run)
    except Exception:  # noqa: BLE001
        return None


async def get_wallet_balance() -> float | None:
    """Ulangan hamyonning TON balansini qaytaradi (toncenter orqali)."""
    import aiohttp

    addr = await get_wallet_address()
    if not addr:
        return None
    headers = {}
    if settings.ton_api_key:
        headers["X-API-Key"] = settings.ton_api_key
    try:
        async with aiohttp.ClientSession() as s:
            url = "https://toncenter.com/api/v3/addressInformation"
            async with s.get(url, params={"address": addr}, headers=headers,
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
                nano = int(data.get("balance", 0))
                return round(nano / 1e9, 4)
    except Exception as e:  # noqa: BLE001
        logger.warning("Balansni olishda xatolik: %s", e)
        return None
