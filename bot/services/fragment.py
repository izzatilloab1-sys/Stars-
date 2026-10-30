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


async def get_wallet_version() -> str:
    """Hamyon versiyasi: v4r2 | v5r1 (W5). DB -> .env."""
    v = (await _cfg("wallet_version", settings.wallet_version)).strip().lower()
    return v if v in ("v4r2", "v5r1") else "v5r1"


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
    """TON seed (va ixtiyoriy Fragment cookie) orqali avtomatik Stars sotib oladi.

    Eslatma: ba'zi kutubxonalar (masalan fragment-api-lib) KYC'SIZ rejimda
    faqat FAOL TON hamyon (seed) bilan ishlaydi — cookie shart emas. KYC rejimда
    cookie ham kerak. Shuning uchun cookie majburiy emas; faqat seed majburiy.

    Mavjud kutubxonalardan birini sinab ko'radi. Buy xatosiz o'tsa -> ok=True.
    """
    seed = (await get_wallet_seed()).strip()
    cookies = await _fragment_cookies()
    wallet_version = await get_wallet_version()

    # Seed MAJBURIY (to'lov manbai). Cookie — ixtiyoriy (KYC rejimida kerak).
    if not seed:
        return DeliveryResult(ok=False, message="Hamyon seed sozlanmagan (admin panel yoki .env).")

    # --- Adapter 1: fragment-api-lib (NightStrang6r) — aniq, asosiy ---
    try:
        return await _try_fragment_api_lib(username, stars, seed, cookies, wallet_version)
    except ImportError:
        logger.info("fragment-api-lib topilmadi, keyingi adapterni sinayman.")
    except Exception as e:  # noqa: BLE001
        logger.exception("fragment-api-lib orqali xatolik")
        return DeliveryResult(ok=False, message=f"Fragment xatolik: {e}")

    # --- Adapter 2 (zaxira): fragment-api / fragment-api-py (S1qwy oilasi) ---
    try:
        return await _try_fragment_api(username, stars, seed, cookies)
    except ImportError:
        logger.info("fragment-api topilmadi, keyingi adapterni sinayman.")
    except Exception as e:  # noqa: BLE001
        logger.exception("fragment-api orqali xatolik")
        return DeliveryResult(ok=False, message=f"Fragment xatolik: {e}")

    # --- Adapter 3 (zaxira): pyfragment (bohd4nx) ---
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
            "`pip install fragment-api-lib` qiling."
        ),
    )


async def _try_fragment_api_lib(
    username: str, stars: int, seed: str, cookies: dict, wallet_version: str = "v5r1"
) -> DeliveryResult:
    """fragment-api-lib (NightStrang6r) — ANIQ interfeys.

        from fragment_api_lib.client import FragmentAPIClient
        client = FragmentAPIClient()
        # KYC'siz (faqat seed, cookie shart emas):
        client.buy_stars_without_kyc(username, amount, seed=..., payment_method="ton")
        # KYC bilan (cookie + seed):
        client.buy_stars(username, amount, fragment_cookies=..., seed=..., show_sender=False)

    show_sender=False -> yuboruvchi (sizning profil) ko'rinmaydi.
    """
    def _run() -> DeliveryResult:
        from fragment_api_lib.client import FragmentAPIClient  # type: ignore

        client = FragmentAPIClient()
        pay = settings.fragment_pay_currency.lower()  # "ton" | "usdt"
        wtype = wallet_version                         # "v4r2" | "v5r1" (W5)
        # Recipient search @ belgisisiz username kutadi -> @ ni OLIB TASHLAYMIZ
        uname = username.lstrip("@")
        has_cookie = bool(cookies.get("stel_token"))

        # --- Asosiy yo'l: KYC'siz (faqat seed) ---
        # fragment-api-lib 1.1.0+ (API v3) KYC'siz rejimda FAQAT seed bilan ishlaydi,
        # cookie UMUMAN kerak emas. wallet_type orqali W5 (v5r1) hamyonni ko'rsatamiz.
        err_without_kyc = None
        try:
            res = _call_flexible(
                client.buy_stars_without_kyc,
                username=uname, amount=stars, seed=seed,
                payment_method=pay, wallet_type=wtype,
            )
            ok, tx, err = _interpret_result(res)
            if ok:
                return DeliveryResult(ok=True, message="Fragment orqali yuborildi", tx_id=tx)
            err_without_kyc = err
        except Exception as e:  # noqa: BLE001
            err_without_kyc = str(e)

        # --- Zaxira: KYC (cookie bilan), agar cookie ulangan bo'lsa ---
        if has_cookie:
            cookie_str = _cookies_to_header(cookies)
            res = _call_flexible(
                client.buy_stars,
                username=uname, amount=stars, fragment_cookies=cookie_str,
                seed=seed, show_sender=False, payment_method=pay, wallet_type=wtype,
            )
            ok, tx, err = _interpret_result(res)
            msg = "Fragment orqali yuborildi" if ok else f"Fragment rad etdi: {err or err_without_kyc or 'noma''lum'}"
            return DeliveryResult(ok=ok, message=msg, tx_id=tx)

        # Cookie yo'q va KYC'siz ham ishlamadi
        return DeliveryResult(
            ok=False,
            message=f"Fragment rad etdi: {err_without_kyc or 'noma''lum sabab'}",
        )

    return await asyncio.to_thread(_run)


def _call_flexible(func, **kwargs):
    """Funksiyani chaqiradi; agar biror parametr (masalan wallet_type) qo'llab-
    quvvatlanmasa (TypeError), uni olib tashlab qayta urinadi. Shunday qilib
    kutubxona versiyasi wallet_type'ni bilmasa ham ishlaydi."""
    import inspect
    try:
        sig = inspect.signature(func)
        accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return func(**accepted)
    except (TypeError, ValueError):
        # imzoni o'qib bo'lmasa — avval hammasi bilan, keyin wallet_type'siz
        try:
            return func(**kwargs)
        except TypeError:
            kwargs.pop("wallet_type", None)
            return func(**kwargs)


def _cookies_to_header(cookies: dict) -> str:
    """Cookie dict'ni 'k=v; k=v' Header String ko'rinishiga keltiradi."""
    parts = []
    for k in ("stel_ssid", "stel_dt", "stel_token", "stel_ton_token"):
        v = cookies.get(k)
        if v:
            parts.append(f"{k}={v}")
    return "; ".join(parts)


def _interpret_result(res) -> tuple[bool, str | None, str | None]:
    """Fragment javobini (dict yoki obyekt) -> (ok, tx_id, error)."""
    if isinstance(res, dict):
        # xato bormi?
        err = res.get("error") or res.get("detail") or res.get("message")
        status = str(res.get("status", "")).lower()
        ok = bool(
            res.get("ok", res.get("success", True))
        ) and status not in ("failed", "error", "cancelled")
        # agar aniq error maydoni bo'lsa va ok belgilanmagan bo'lsa
        if err and "ok" not in res and "success" not in res and not status:
            ok = False
        tx = (
            res.get("tx_hash") or res.get("hash") or res.get("transaction")
            or res.get("order_uuid") or res.get("order_id") or res.get("id")
        )
        return ok, (str(tx) if tx else None), (str(err) if err else None)
    # obyekt
    ok = getattr(res, "ok", getattr(res, "success", True))
    tx = (
        getattr(res, "tx_hash", None) or getattr(res, "hash", None)
        or getattr(res, "order_uuid", None) or getattr(res, "order_id", None)
    )
    err = getattr(res, "error", None) or getattr(res, "message", None)
    return bool(ok), (str(tx) if tx else None), (str(err) if err else None)


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

        seed_words = seed.split()
        # Klientni yaratish — cookie'li va cookie'siz (KYC'siz) rejimni sinaymiz
        has_cookie = bool(cookies.get("stel_token"))
        api = None
        for kwargs in (
            ({"cookies": cookies, "seed": seed_words} if has_cookie else None),
            {"seed": seed_words},              # KYC'siz: faqat seed
            {"seed": seed},                     # seed string ko'rinishida
        ):
            if kwargs is None:
                continue
            try:
                api = FragmentAPI(**kwargs)
                break
            except TypeError:
                continue
        if api is None:
            api = FragmentAPI(seed=seed_words)

        pay = settings.fragment_pay_currency.lower()  # "ton" | "usdt"
        # buy_stars'ni turli parametr kombinatsiyalari bilan sinaymiz
        # (account_index — 12 so'zli seed uchun ba'zi kutubxonalarда kerak)
        res = None
        last_err: Exception | None = None
        attempts = [
            {"username": username, "amount": stars, "payment_method": pay, "account_index": 0},
            {"username": username, "amount": stars, "payment_method": pay},
            {"username": username, "amount": stars},
        ]
        for kw in attempts:
            try:
                res = api.buy_stars(**kw)
                break
            except TypeError as e:
                last_err = e
                continue
        if res is None:
            raise last_err or RuntimeError("buy_stars chaqirib bo'lmadi (interfeys mos emas)")

        # Natija formati kutubxonaga bog'liq: dict yoki obyekt
        tx, ok, err = None, True, None
        if isinstance(res, dict):
            ok = bool(res.get("ok", res.get("success", True)))
            tx = res.get("tx_hash") or res.get("hash") or res.get("transaction")
            err = res.get("error") or res.get("message")
        else:
            tx = getattr(res, "tx_hash", None) or getattr(res, "hash", None)
            ok = getattr(res, "ok", getattr(res, "success", True))
            err = getattr(res, "error", None)
        msg = "Fragment orqali yuborildi" if ok else f"Fragment rad etdi: {err or 'noma''lum sabab'}"
        return DeliveryResult(ok=ok, message=msg, tx_id=tx)

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
    wallet_version = await get_wallet_version()
    return {
        "mode": mode,
        "seed_set": bool(seed),
        "seed_words": seed_words,
        "cookie_set": bool(cookies.get("stel_token")),
        "wallet_version": wallet_version,
        "wallet_address": await get_wallet_address(seed, wallet_version) if seed else None,
        "tg_set": bool(tg_session),
        "tg_api_set": bool(tg_api_id and tg_api_id != "0" and tg_api_hash),
    }


async def get_wallet_address(seed: str | None = None, wallet_version: str | None = None) -> str | None:
    """Seed'dan hamyon manzilini hisoblaydi (ko'rsatish uchun).

    wallet_version: v4r2 | v5r1 (W5). Tonkeeper yangi hamyonlar odatda v5r1."""
    if seed is None:
        seed = (await get_wallet_seed()).strip()
    if not seed:
        return None
    if wallet_version is None:
        wallet_version = await get_wallet_version()

    def _run() -> str | None:
        try:
            from tonutils.client import TonapiClient  # type: ignore
        except ImportError:
            return None
        client = TonapiClient(api_key=settings.ton_api_key or "")
        words = seed.split()
        # Versiyaga mos wallet klassini tanlaymiz; topilmasa ikkalasini sinaymiz
        candidates = []
        try:
            from tonutils.wallet import WalletV5R1  # type: ignore
            candidates.append(("v5r1", WalletV5R1))
        except ImportError:
            pass
        try:
            from tonutils.wallet import WalletV4R2  # type: ignore
            candidates.append(("v4r2", WalletV4R2))
        except ImportError:
            pass
        # Avval so'ralgan versiyani, keyin qolganini sinaymiz
        candidates.sort(key=lambda c: 0 if c[0] == wallet_version else 1)
        for _, cls in candidates:
            try:
                wallet, _, _, _ = cls.from_mnemonic(client, words)
                return wallet.address.to_str()
            except Exception:  # noqa: BLE001
                continue
        return None

    try:
        return await asyncio.to_thread(_run)
    except Exception:  # noqa: BLE001
        return None


async def get_wallet_balance() -> float | None:
    """Ulangan hamyonning TON balansini qaytaradi.

    Avval fragment-api-lib ning get_balance(seed) metodi (eng aniq — Fragment
    ishlatadigan AYNI hamyonni biladi), keyin zaxira sifatida toncenter orqali
    hamyon manzili balansi."""
    seed = (await get_wallet_seed()).strip()
    if not seed:
        return None

    wallet_version = await get_wallet_version()

    # --- 1-usul: fragment-api-lib get_balance (W5'ni biladi) ---
    # DIQQAT: kutubxona ba'zan xato tufayli 0.0 qaytaradi (None emas). Shuning uchun
    # faqat MUSBAT (>0) qiymatni ishonchli deb qabul qilamiz; 0 yoki None bo'lsa
    # toncenter zaxirasiga o'tamiz (u haqiqiy balansni aniq beradi).
    bal = await _balance_via_fragment_lib(seed, wallet_version)
    if bal is not None and bal > 0:
        return bal

    # --- 2-usul (zaxira, ishonchli): toncenter addressInformation ---
    ton_bal = await _balance_via_toncenter()
    if ton_bal is not None:
        return ton_bal

    # toncenter ham bo'lmasa, lib qaytargan qiymat (0.0) ni qaytaramiz
    return bal


async def _balance_via_fragment_lib(seed: str, wallet_version: str = "v5r1") -> float | None:
    """fragment-api-lib orqali TON balansi (wallet_type bilan — W5'ni qo'llaydi)."""
    def _run() -> float | None:
        try:
            from fragment_api_lib.client import FragmentAPIClient  # type: ignore
        except ImportError:
            return None
        client = FragmentAPIClient()
        # get_balance (seed) yoki get_balance_v2 (wallet_type) — qaysi biri ishlasa
        for func, kwargs in (
            (getattr(client, "get_balance", None), {"seed": seed, "wallet_type": wallet_version}),
            (getattr(client, "get_balance_v2", None), {"seed": seed, "wallet_type": wallet_version}),
            (getattr(client, "get_balance", None), {"seed": seed}),
        ):
            if func is None:
                continue
            try:
                res = _call_flexible(func, **kwargs)
                bal = _parse_balance(res)
                if bal is not None:
                    return bal
            except Exception as e:  # noqa: BLE001
                logger.warning("fragment-api-lib balans xato (%s): %s", wallet_version, e)
                continue
        return None

    return await asyncio.to_thread(_run)


def _parse_balance(res) -> float | None:
    """get_balance javobidan TON summasini ajratadi (turli formatlar)."""
    if res is None:
        return None
    # dict bo'lsa: balance / ton / amount / available maydonlarini qidiramiz
    if isinstance(res, dict):
        for key in ("balance", "ton", "amount", "available", "ton_balance"):
            if key in res and res[key] is not None:
                try:
                    val = float(res[key])
                    # nano-TON bo'lsa (juda katta son) -> TON ga aylantiramiz
                    return round(val / 1e9, 4) if val > 1e6 else round(val, 4)
                except (TypeError, ValueError):
                    continue
        # data ichida bo'lishi mumkin
        if isinstance(res.get("data"), dict):
            return _parse_balance(res["data"])
        return None
    # son bo'lsa
    try:
        val = float(res)
        return round(val / 1e9, 4) if val > 1e6 else round(val, 4)
    except (TypeError, ValueError):
        return None


async def _balance_via_toncenter() -> float | None:
    """toncenter v3 addressInformation orqali hamyon balansi (zaxira)."""
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
            async with s.get(url, params={"address": addr, "use_v2": "false"},
                             headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as r:
                data = await r.json()
                # v3 javobi: {"balance": "123456789", ...} yoki nested
                raw = data.get("balance")
                if raw is None and isinstance(data.get("result"), dict):
                    raw = data["result"].get("balance")
                nano = int(raw or 0)
                return round(nano / 1e9, 4)
    except Exception as e:  # noqa: BLE001
        logger.warning("toncenter balansni olishda xatolik: %s", e)
        return None


def _fragment_lib_installed() -> str | None:
    """O'rnatilgan Fragment kutubxonasi nomini qaytaradi (yoki None)."""
    for name in ("fragment_api_lib", "fragment_api", "fragment_api_py", "pyfragment"):
        try:
            __import__(name)
            return name
        except ImportError:
            continue
    return None


async def auto_delivery_diagnostics() -> dict:
    """Avtomatik yetkazish uchun barcha shartlarni tekshiradi.

    Qaytaradi: har bir shart holati + umumiy 'ready' (tayyormi)."""
    mode = await get_fragment_mode()
    seed = (await get_wallet_seed()).strip()
    cookies = await _fragment_cookies()
    lib = _fragment_lib_installed()

    # Cookie endi MAJBURIY EMAS: fragment-api-lib 1.1.0+ KYC'siz rejimda faqat
    # seed bilan ishlaydi. Shuning uchun 'ready' uchun cookie shart emas.
    checks = {
        "mode_fragment": mode == "fragment",
        "seed_set": bool(seed),
        "lib_installed": lib is not None,
    }
    return {
        "mode": mode,
        "lib_name": lib,
        "checks": checks,
        "cookie_set": bool(cookies.get("stel_token")),  # faqat ko'rsatish uchun (ixtiyoriy)
        "ready": all(checks.values()),
    }
