"""Ma'lumotlar bazasi bilan ishlash funksiyalari."""
from __future__ import annotations

import datetime as dt
import random

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.database.models import (
    Base,
    Order,
    OrderStatus,
    Promocode,
    PromoUse,
    RequiredChannel,
    Setting,
    Task,
    TaskCompletion,
    Topup,
    User,
    Withdrawal,
    WithdrawalStatus,
)

engine = create_async_engine("sqlite+aiosqlite:///stars_bot.db", echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------- Users ----------
async def get_or_create_user(
    user_id: int,
    username: str | None,
    full_name: str | None,
    referrer_id: int | None = None,
) -> tuple[User, bool]:
    """Foydalanuvchini qaytaradi. (user, yangi_yaratildimi)."""
    async with Session() as s:
        user = await s.get(User, user_id)
        if user:
            # username/ism yangilansin
            user.username = username
            user.full_name = full_name
            await s.commit()
            return user, False

        # o'zini o'ziga referal qila olmaydi
        if referrer_id == user_id:
            referrer_id = None
        # referrer mavjudligini tekshirish
        if referrer_id is not None:
            ref = await s.get(User, referrer_id)
            if ref is None:
                referrer_id = None

        user = User(
            id=user_id,
            username=username,
            full_name=full_name,
            referrer_id=referrer_id,
        )
        s.add(user)
        await s.commit()
        return user, True


async def get_user(user_id: int) -> User | None:
    async with Session() as s:
        return await s.get(User, user_id)


async def add_balance(user_id: int, amount: int) -> None:
    async with Session() as s:
        await s.execute(
            update(User).where(User.id == user_id).values(balance=User.balance + amount)
        )
        await s.commit()


async def add_stars(user_id: int, amount: int) -> None:
    """Foydalanuvchining Stars bonus balansiga qo'shadi (manfiy bo'lsa ayiradi)."""
    async with Session() as s:
        await s.execute(
            update(User)
            .where(User.id == user_id)
            .values(stars_balance=User.stars_balance + amount)
        )
        await s.commit()


async def get_stars_balance(user_id: int) -> int:
    """Foydalanuvchining Stars bonus balansi."""
    async with Session() as s:
        user = await s.get(User, user_id)
        return int(user.stars_balance) if user else 0


async def set_banned(user_id: int, banned: bool) -> None:
    async with Session() as s:
        await s.execute(
            update(User).where(User.id == user_id).values(is_banned=banned)
        )
        await s.commit()


async def count_referrals(user_id: int) -> int:
    async with Session() as s:
        res = await s.execute(
            select(func.count()).select_from(User).where(User.referrer_id == user_id)
        )
        return int(res.scalar() or 0)


# ---------- Orders ----------
async def create_order(
    user_id: int,
    target_username: str,
    stars: int,
    amount: int,
    bonus_used: int,
    payment_method: str,
) -> Order:
    async with Session() as s:
        order = Order(
            user_id=user_id,
            target_username=target_username,
            stars=stars,
            amount=amount,
            bonus_used=bonus_used,
            payment_method=payment_method,
            status=OrderStatus.PENDING,
        )
        s.add(order)
        await s.commit()
        await s.refresh(order)
        return order


async def get_order(order_id: int) -> Order | None:
    async with Session() as s:
        return await s.get(Order, order_id)


async def set_order_field(order_id: int, **fields) -> None:
    """Buyurtmaning ixtiyoriy maydon(lar)ini yangilaydi."""
    async with Session() as s:
        await s.execute(update(Order).where(Order.id == order_id).values(**fields))
        await s.commit()


async def get_order_by_comment(comment: str) -> Order | None:
    """TON to'lov comment'i bo'yicha buyurtmani topadi."""
    async with Session() as s:
        res = await s.execute(select(Order).where(Order.pay_comment == comment))
        return res.scalar_one_or_none()


async def mark_paid_if_pending(order_id: int, payment_id: str | None = None) -> bool:
    """Buyurtma PENDING bo'lsa, uni atomik tarzda PAID qiladi.
    Qaytaradi: True — agar shu chaqiruv uni PAID qilgan bo'lsa (ya'ni birinchi marta).
    Ikki marta yetkazishning oldini oladi."""
    async with Session() as s:
        values: dict = {"status": OrderStatus.PAID}
        if payment_id is not None:
            values["payment_id"] = payment_id
        res = await s.execute(
            update(Order)
            .where(Order.id == order_id, Order.status == OrderStatus.PENDING)
            .values(**values)
        )
        await s.commit()
        return res.rowcount > 0


async def set_order_status(
    order_id: int, status: OrderStatus, payment_id: str | None = None
) -> None:
    async with Session() as s:
        values: dict = {"status": status}
        if payment_id is not None:
            values["payment_id"] = payment_id
        await s.execute(update(Order).where(Order.id == order_id).values(**values))
        await s.commit()


async def get_user_orders(user_id: int, limit: int = 10) -> list[Order]:
    async with Session() as s:
        res = await s.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.id.desc())
            .limit(limit)
        )
        return list(res.scalars().all())


# ---------- Referral bonus on paid order ----------
async def apply_referral_bonus(order_id: int, bonus_percent: int) -> tuple[int, int] | None:
    """To'langan buyurtma uchun referrerga bonus beradi.

    Mukofot ikki usulda hisoblanadi:
      - Agar settings['referral_stars'] > 0 bo'lsa: har referal BUYURTMASIGA
        belgilangan Stars soni × 1 Star narxi = so'mdagi bonus beriladi.
      - Aks holda: buyurtma summasidan bonus_percent foiz beriladi.

    Qaytaradi: (referrer_id, bonus_amount_som) yoki None.
    Eslatma: bonus faqat referral'ning BIRINCHI to'langan buyurtmasida beriladi."""
    async with Session() as s:
        order = await s.get(Order, order_id)
        if not order:
            return None
        user = await s.get(User, order.user_id)
        if not user or user.referrer_id is None:
            return None

        # Bu referral'ning birinchi muvaffaqiyatli buyurtmasimi? (takroriy bonusdan himoya)
        prev = await s.execute(
            select(func.count()).select_from(Order).where(
                Order.user_id == user.id,
                Order.id != order_id,
                Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERING, OrderStatus.DONE]),
            )
        )
        if int(prev.scalar() or 0) > 0:
            return None  # avval ham buyurtma qilgan — referal bonusi allaqachon berilgan

        # Mukofotni hisoblaymiz
        ref_stars_raw = await s.get(Setting, "referral_stars")
        ref_stars = int(ref_stars_raw.value) if ref_stars_raw and ref_stars_raw.value.isdigit() else 0
        if ref_stars > 0:
            price_raw = await s.get(Setting, "price_per_star")
            from bot.config import settings as _s
            price = int(price_raw.value) if price_raw and price_raw.value.isdigit() else _s.price_per_star
            bonus = ref_stars * price
        else:
            bonus = order.amount * bonus_percent // 100

        if bonus <= 0:
            return None
        await s.execute(
            update(User)
            .where(User.id == user.referrer_id)
            .values(balance=User.balance + bonus)
        )
        await s.commit()
        return user.referrer_id, bonus


# ---------- Promocodes ----------
async def create_promocode(
    code: str,
    bonus_amount: int,
    max_uses: int,
    reward_type: str = "som",
) -> Promocode:
    async with Session() as s:
        promo = Promocode(
            code=code,
            bonus_amount=bonus_amount,
            max_uses=max_uses,
            reward_type=reward_type if reward_type in ("som", "stars") else "som",
        )
        s.add(promo)
        await s.commit()
        await s.refresh(promo)
        return promo


class RedeemResult:
    """Promokod ishlatish natijasi (kanal postini yangilash uchun ma'lumot bilan)."""
    def __init__(self, ok: bool, message: str, amount: int = 0,
                 reward_type: str = "som", promo: Promocode | None = None):
        self.ok = ok
        self.message = message
        self.amount = amount
        self.reward_type = reward_type
        self.promo = promo  # muvaffaqiyatli bo'lsa — yangilangan promokod (post uchun)


async def redeem_promocode(user_id: int, code: str) -> RedeemResult:
    """Promokodni ATOMIK ishlatadi (Stars yoki so'm). 1 akkaunt = 1 marta.

    Qaytaradi: RedeemResult (ok, xabar, miqdor, tur, promo). promo — kanal postini
    yangilash uchun (channel_chat_id/message_id, used_count, max_uses, channel_text)."""
    code = code.strip()
    async with Session() as s:
        res = await s.execute(select(Promocode).where(func.lower(Promocode.code) == code.lower()))
        promo = res.scalar_one_or_none()
        if not promo or not promo.is_active:
            return RedeemResult(False, "Bunday promokod topilmadi yoki faol emas.")
        if promo.used_count >= promo.max_uses:
            return RedeemResult(False, "Afsuski, promokod limiti tugagan.")

        rtype = promo.reward_type or "som"

        # ATOMIK: PromoUse insert + flush. IntegrityError (UNIQUE) -> allaqachon ishlatgan.
        s.add(PromoUse(promo_id=promo.id, user_id=user_id))
        try:
            await s.flush()
        except IntegrityError:
            await s.rollback()
            return RedeemResult(False, "Siz bu promokodni allaqachon ishlatgansiz.")

        # Limitni atomik oshiramiz (faqat limit tugamagan bo'lsa)
        upd = await s.execute(
            update(Promocode)
            .where(Promocode.id == promo.id, Promocode.used_count < Promocode.max_uses)
            .values(used_count=Promocode.used_count + 1)
        )
        if upd.rowcount == 0:
            # Boshqa so'rov ayni paytda limitni to'ldirib qo'ydi
            await s.rollback()
            return RedeemResult(False, "Afsuski, promokod limiti tugagan.")

        # Balansga qo'shamiz (turiga qarab)
        if rtype == "stars":
            await s.execute(
                update(User).where(User.id == user_id)
                .values(stars_balance=User.stars_balance + promo.bonus_amount)
            )
            msg = f"✅ Promokod qabul qilindi! +{promo.bonus_amount:,} ⭐ bonus."
        else:
            await s.execute(
                update(User).where(User.id == user_id)
                .values(balance=User.balance + promo.bonus_amount)
            )
            msg = f"✅ Promokod qabul qilindi! +{promo.bonus_amount:,} so'm bonus."

        await s.commit()
        await s.refresh(promo)
        return RedeemResult(True, msg, promo.bonus_amount, rtype, promo)


# ---------- Promokod — admin ro'yxat/boshqaruv ----------
async def list_promocodes(limit: int = 50) -> list[Promocode]:
    async with Session() as s:
        res = await s.execute(select(Promocode).order_by(Promocode.id.desc()).limit(limit))
        return list(res.scalars().all())


async def get_promocode(promo_id: int) -> Promocode | None:
    async with Session() as s:
        return await s.get(Promocode, promo_id)


async def set_promocode_channel(promo_id: int, chat_id: str, message_id: int, text: str) -> None:
    async with Session() as s:
        await s.execute(
            update(Promocode).where(Promocode.id == promo_id).values(
                channel_chat_id=chat_id, channel_message_id=message_id, channel_text=text
            )
        )
        await s.commit()


async def set_promocode_active(promo_id: int, active: bool) -> None:
    async with Session() as s:
        await s.execute(
            update(Promocode).where(Promocode.id == promo_id).values(is_active=active)
        )
        await s.commit()


async def delete_promocode(promo_id: int) -> None:
    async with Session() as s:
        await s.execute(PromoUse.__table__.delete().where(PromoUse.promo_id == promo_id))
        promo = await s.get(Promocode, promo_id)
        if promo:
            await s.delete(promo)
        await s.commit()


async def get_promo_users(promo_id: int, limit: int = 100) -> list[dict]:
    """Promokodni ishlatgan foydalanuvchilar: user_id + username + ism."""
    async with Session() as s:
        res = await s.execute(
            select(User.id, User.username, User.full_name)
            .join(PromoUse, PromoUse.user_id == User.id)
            .where(PromoUse.promo_id == promo_id)
            .order_by(PromoUse.id.desc())
            .limit(limit)
        )
        return [
            {"id": row[0], "username": row[1], "full_name": row[2]}
            for row in res.all()
        ]


# ---------- Topup (balans to'ldirish) ----------
async def create_topup(user_id: int, amount: int, payment_method: str) -> Topup:
    async with Session() as s:
        t = Topup(user_id=user_id, amount=amount, payment_method=payment_method,
                  status=OrderStatus.PENDING)
        s.add(t)
        await s.commit()
        await s.refresh(t)
        return t


async def get_topup(topup_id: int) -> Topup | None:
    async with Session() as s:
        return await s.get(Topup, topup_id)


async def set_topup_field(topup_id: int, **fields) -> None:
    async with Session() as s:
        await s.execute(update(Topup).where(Topup.id == topup_id).values(**fields))
        await s.commit()


async def complete_topup_if_pending(topup_id: int, payment_id: str | None = None) -> bool:
    """Topup PENDING bo'lsa, atomik PAID qiladi va foydalanuvchi balansiga qo'shadi.
    Qaytaradi: True — agar shu chaqiruv bajargan bo'lsa (ikki marta qo'shishdan himoya)."""
    async with Session() as s:
        values: dict = {"status": OrderStatus.PAID}
        if payment_id is not None:
            values["payment_id"] = payment_id
        res = await s.execute(
            update(Topup)
            .where(Topup.id == topup_id, Topup.status == OrderStatus.PENDING)
            .values(**values)
        )
        if res.rowcount == 0:
            await s.commit()
            return False
        # balansga qo'shamiz
        t = await s.get(Topup, topup_id)
        await s.execute(
            update(User).where(User.id == t.user_id).values(balance=User.balance + t.amount)
        )
        await s.commit()
        return True


async def get_topup_by_comment(comment: str) -> Topup | None:
    async with Session() as s:
        res = await s.execute(select(Topup).where(Topup.pay_comment == comment))
        return res.scalar_one_or_none()


# ---------- Karta (avto) — noyob summa band qilish ----------
async def create_card_topup(user_id: int, base_amount: int, ttl_minutes: int = 15) -> Topup | None:
    """Karta (avto) uchun NOYOB summali topup yaratadi.

    base_amount ga 1..99 so'm qo'shib, AYNI SHU DAQIQADA boshqa faol (PENDING,
    muddati tugamagan) topup'da band bo'lmagan noyob summa tanlaydi. Shu summa
    kartaga tashlanishi kerak — bank xabari shu summaga mos kelsa, to'lov topiladi.

    Qaytaradi: Topup (expected_amount, expires_at bilan) yoki None (bo'sh summa
    topilmasa — juda kam ehtimol)."""
    now = dt.datetime.now(dt.timezone.utc)
    expires = now + dt.timedelta(minutes=ttl_minutes)
    async with Session() as s:
        # Hozir band bo'lgan (faol) expected_amount'lar
        res = await s.execute(
            select(Topup.expected_amount).where(
                Topup.payment_method == "card",
                Topup.status == OrderStatus.PENDING,
                Topup.expires_at > now,
                Topup.expected_amount.is_not(None),
            )
        )
        taken = {row[0] for row in res.all()}
        # 1..99 oralig'idan bo'sh qo'shimchani tasodifiy tanlaymiz
        candidates = list(range(1, 100))
        random.shuffle(candidates)
        chosen = None
        for extra in candidates:
            if (base_amount + extra) not in taken:
                chosen = base_amount + extra
                break
        if chosen is None:
            return None  # barcha 99 variant band (favqulodda holat)

        t = Topup(
            user_id=user_id,
            amount=base_amount,            # balansga qo'shiladigan asosiy summa
            expected_amount=chosen,         # kartaga tashlanadigan noyob summa
            expires_at=expires,
            payment_method="card",
            status=OrderStatus.PENDING,
        )
        s.add(t)
        await s.commit()
        await s.refresh(t)
        return t


async def find_card_topup_by_amount(received_amount: int) -> Topup | None:
    """Kartaga kelgan summa bo'yicha faol (PENDING, muddati tugamagan) karta
    topup'ini topadi. Telethon listener shu funksiyani ishlatadi."""
    now = dt.datetime.now(dt.timezone.utc)
    async with Session() as s:
        res = await s.execute(
            select(Topup).where(
                Topup.payment_method == "card",
                Topup.status == OrderStatus.PENDING,
                Topup.expected_amount == received_amount,
                Topup.expires_at > now,
            ).order_by(Topup.id.asc())
        )
        return res.scalars().first()


async def expire_old_card_topups() -> int:
    """Muddati tugagan faol karta topup'larini FAILED qiladi (tozalash)."""
    now = dt.datetime.now(dt.timezone.utc)
    async with Session() as s:
        res = await s.execute(
            update(Topup)
            .where(
                Topup.payment_method == "card",
                Topup.status == OrderStatus.PENDING,
                Topup.expires_at < now,
            )
            .values(status=OrderStatus.FAILED)
        )
        await s.commit()
        return res.rowcount or 0


# ---------- Settings (admin panel orqali sozlash) ----------
async def set_setting(key: str, value: str) -> None:
    async with Session() as s:
        obj = await s.get(Setting, key)
        if obj:
            obj.value = value
        else:
            s.add(Setting(key=key, value=value))
        await s.commit()


async def get_setting(key: str, default: str = "") -> str:
    async with Session() as s:
        obj = await s.get(Setting, key)
        return obj.value if obj and obj.value else default


async def get_all_settings() -> dict[str, str]:
    async with Session() as s:
        res = await s.execute(select(Setting))
        return {row.key: row.value for row in res.scalars().all()}


# ---------- Admin / Owner boshqaruvi ----------
async def get_db_admins() -> list[int]:
    """DB'da qo'shilgan admin ID'lari (settings['admins'] = '111,222')."""
    raw = await get_setting("admins", "")
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


async def add_db_admin(user_id: int) -> None:
    admins = await get_db_admins()
    if user_id not in admins:
        admins.append(user_id)
        await set_setting("admins", ",".join(str(x) for x in admins))


async def remove_db_admin(user_id: int) -> None:
    admins = await get_db_admins()
    admins = [x for x in admins if x != user_id]
    await set_setting("admins", ",".join(str(x) for x in admins))


async def get_owner() -> int | None:
    """Bot egasi ID (settings['owner']). O'rnatilmagan bo'lsa None."""
    raw = await get_setting("owner", "")
    return int(raw) if raw.isdigit() else None


async def set_owner(user_id: int) -> None:
    await set_setting("owner", str(user_id))


# ---------- Narx va referal sozlamalari (admin panel orqali) ----------
async def get_price_per_star() -> int:
    """1 Star narxi (so'm). DB -> .env."""
    from bot.config import settings as _s
    raw = await get_setting("price_per_star", "")
    return int(raw) if raw.isdigit() else _s.price_per_star


async def set_price_per_star(price: int) -> None:
    await set_setting("price_per_star", str(price))


async def get_referral_stars() -> int:
    """1 ta referal uchun beriladigan Stars soni (default 0)."""
    raw = await get_setting("referral_stars", "")
    return int(raw) if raw.isdigit() else 0


async def set_referral_stars(stars: int) -> None:
    await set_setting("referral_stars", str(stars))


# ---------- Withdrawals (Stars yechib olish) ----------
async def create_withdrawal(user_id: int, stars: int) -> Withdrawal | None:
    """Stars yechib olish zayafkasini yaratadi.

    Bir sessiyada: foydalanuvchining stars_balance >= stars ekanini atomik
    tekshiradi va ayiradi (hold). Faqat ayirish muvaffaqiyatli bo'lsa Withdrawal
    qatorini qo'shadi. Yetarli Stars bo'lmasa None qaytaradi."""
    async with Session() as s:
        res = await s.execute(
            update(User)
            .where(User.id == user_id, User.stars_balance >= stars)
            .values(stars_balance=User.stars_balance - stars)
        )
        if res.rowcount == 0:
            await s.commit()
            return None
        wd = Withdrawal(user_id=user_id, stars=stars, status=WithdrawalStatus.PENDING)
        s.add(wd)
        await s.commit()
        await s.refresh(wd)
        return wd


async def get_withdrawal(withdrawal_id: int) -> Withdrawal | None:
    async with Session() as s:
        return await s.get(Withdrawal, withdrawal_id)


async def mark_withdrawal_paid_if_pending(withdrawal_id: int) -> bool:
    """Zayafka PENDING bo'lsa atomik PAID qiladi.
    Qaytaradi: True, agar shu chaqiruv bajargan bo'lsa (takroriydan himoya)."""
    async with Session() as s:
        res = await s.execute(
            update(Withdrawal)
            .where(
                Withdrawal.id == withdrawal_id,
                Withdrawal.status == WithdrawalStatus.PENDING,
            )
            .values(status=WithdrawalStatus.PAID)
        )
        await s.commit()
        return res.rowcount > 0


async def cancel_withdrawal_if_pending(withdrawal_id: int) -> bool:
    """Zayafka PENDING bo'lsa atomik CANCELLED qiladi va faqat shunda ushlab
    qolingan Stars'ni foydalanuvchi balansiga qaytaradi.
    Qaytaradi: True, agar shu chaqiruv bekor qilgan bo'lsa (takroriy qaytarishdan himoya)."""
    async with Session() as s:
        res = await s.execute(
            update(Withdrawal)
            .where(
                Withdrawal.id == withdrawal_id,
                Withdrawal.status == WithdrawalStatus.PENDING,
            )
            .values(status=WithdrawalStatus.CANCELLED)
        )
        if res.rowcount == 0:
            await s.commit()
            return False
        wd = await s.get(Withdrawal, withdrawal_id)
        await s.execute(
            update(User)
            .where(User.id == wd.user_id)
            .values(stars_balance=User.stars_balance + wd.stars)
        )
        await s.commit()
        return True


# ---------- Tasks (Stars ishlash, reklama kanallari) ----------
async def create_task(
    channel_id: str, title: str | None, reward_stars: int, invite_link: str | None = None
) -> Task:
    async with Session() as s:
        task = Task(
            channel_id=channel_id,
            title=title,
            reward_stars=reward_stars,
            invite_link=invite_link,
        )
        s.add(task)
        await s.commit()
        await s.refresh(task)
        return task


async def get_task(task_id: int) -> Task | None:
    async with Session() as s:
        return await s.get(Task, task_id)


async def get_active_tasks() -> list[Task]:
    async with Session() as s:
        res = await s.execute(
            select(Task).where(Task.is_active == True).order_by(Task.id.asc())  # noqa: E712
        )
        return list(res.scalars().all())


async def set_task_active(task_id: int, active: bool) -> None:
    async with Session() as s:
        await s.execute(update(Task).where(Task.id == task_id).values(is_active=active))
        await s.commit()


async def set_task_invite_link(task_id: int, link: str | None) -> None:
    async with Session() as s:
        await s.execute(update(Task).where(Task.id == task_id).values(invite_link=link))
        await s.commit()


async def complete_task_if_new(task_id: int, user_id: int, reward_stars: int) -> bool:
    """Agar (task,user) uchun TaskCompletion mavjud bo'lmasa, uni qo'shadi va
    stars_balance += reward_stars qiladi. Qaytaradi: True faqat birinchi marta
    bajarilganda (takroriy to'lovdan himoya).

    Poyga (race) himoyasi: avval tezkor mavjudlik tekshiruvi qilinadi, so'ng
    TaskCompletion INSERT qilinib flush orqali bazaga yuboriladi. Bir vaqtda
    kelgan ikkinchi bosilish (task_id, user_id) UNIQUE cheklovini buzadi va
    IntegrityError bilan tushadi — bu holda hech narsa qo'shilmaydi va False
    qaytariladi. Stars kreditlash faqat INSERT muvaffaqiyatli bo'lgandagina
    amalga oshiriladi."""
    async with Session() as s:
        exists = await s.execute(
            select(TaskCompletion.id).where(
                TaskCompletion.task_id == task_id,
                TaskCompletion.user_id == user_id,
            )
        )
        if exists.scalar_one_or_none():
            return False  # tezkor yo'l (fast path)
        s.add(TaskCompletion(task_id=task_id, user_id=user_id))
        try:
            # UNIQUE cheklovini hoziroq ishga tushiramiz (commit'dan oldin)
            await s.flush()
        except IntegrityError:
            # Poyga: boshqa bosilish allaqachon qo'shib ulgurgan
            await s.rollback()
            return False
        await s.execute(
            update(User)
            .where(User.id == user_id)
            .values(stars_balance=User.stars_balance + reward_stars)
        )
        await s.commit()
        return True


async def count_user_task_completions(user_id: int) -> int:
    async with Session() as s:
        res = await s.execute(
            select(func.count())
            .select_from(TaskCompletion)
            .where(TaskCompletion.user_id == user_id)
        )
        return int(res.scalar() or 0)


async def has_completed_task(task_id: int, user_id: int) -> bool:
    async with Session() as s:
        res = await s.execute(
            select(TaskCompletion).where(
                TaskCompletion.task_id == task_id,
                TaskCompletion.user_id == user_id,
            )
        )
        return res.scalar_one_or_none() is not None


async def get_referrals_with_task_counts(
    referrer_id: int, limit: int = 50
) -> tuple[list[tuple[User, int]], int]:
    """Berilgan foydalanuvchi (referrer_id) chaqirgan referallarni qaytaradi.

    Har bir element: (User, bajarilgan_zadaniyalar_soni).
    Qaytaradi: (rows, total) — rows limit bilan cheklangan, total esa umumiy son."""
    async with Session() as s:
        total_res = await s.execute(
            select(func.count())
            .select_from(User)
            .where(User.referrer_id == referrer_id)
        )
        total = int(total_res.scalar() or 0)

        res = await s.execute(
            select(User)
            .where(User.referrer_id == referrer_id)
            .order_by(User.created_at.desc())
            .limit(limit)
        )
        users = list(res.scalars().all())

        rows: list[tuple[User, int]] = []
        for u in users:
            cnt_res = await s.execute(
                select(func.count())
                .select_from(TaskCompletion)
                .where(TaskCompletion.user_id == u.id)
            )
            rows.append((u, int(cnt_res.scalar() or 0)))
        return rows, total


async def maybe_reward_referrer_for_tasks(user_id: int) -> tuple[int, int] | None:
    """Referal (user_id) yetarlicha zadaniya bajargan bo'lsa, uni taklif qilgan
    odamga bir martalik Stars bonusini beradi.

    Qadamlar:
      1. user_id ning referrer_id sini topadi (None bo'lsa — None qaytaradi).
      2. Bu referal uchun avval bonus berilmaganini tekshiradi (ref_bonus_given).
      3. Bajargan zadaniyalar soni >= get_referral_task_threshold() bo'lsa,
         atomik tarzda ref_bonus_given=True qiladi (UPDATE ... WHERE ref_bonus_given=False,
         rowcount tekshiriladi) va faqat shundagina referrerga Stars qo'shadi.

    Qaytaradi: (referrer_id, reward_stars) — agar bonus berilgan bo'lsa, aks holda None.
    referral_stars sozlamasi 0 bo'lsa, bonus 0 hisoblanadi va o'tkazib yuboriladi
    (bonus endi faqat Stars ko'rinishida)."""
    reward_stars = await get_referral_stars()
    if reward_stars <= 0:
        return None
    threshold = await get_referral_task_threshold()

    async with Session() as s:
        user = await s.get(User, user_id)
        if not user or user.referrer_id is None:
            return None
        if user.ref_bonus_given:
            return None
        referrer_id = user.referrer_id

        # Bajarilgan zadaniyalar soni
        cnt_res = await s.execute(
            select(func.count())
            .select_from(TaskCompletion)
            .where(TaskCompletion.user_id == user_id)
        )
        if int(cnt_res.scalar() or 0) < threshold:
            return None

        # Atomik: faqat bayroq hali False bo'lsa True qilamiz
        flag_res = await s.execute(
            update(User)
            .where(User.id == user_id, User.ref_bonus_given == False)  # noqa: E712
            .values(ref_bonus_given=True)
        )
        if flag_res.rowcount == 0:
            await s.commit()
            return None
        # faqat biz bayroqni o'rnatgan bo'lsak referrerga Stars qo'shamiz
        await s.execute(
            update(User)
            .where(User.id == referrer_id)
            .values(stars_balance=User.stars_balance + reward_stars)
        )
        await s.commit()
        return referrer_id, reward_stars


# ---------- Required channels (majburiy obuna) ----------
async def create_required_channel(
    channel_id: str, title: str | None, invite_link: str | None = None
) -> RequiredChannel:
    async with Session() as s:
        ch = RequiredChannel(channel_id=channel_id, title=title, invite_link=invite_link)
        s.add(ch)
        await s.commit()
        await s.refresh(ch)
        return ch


async def get_required_channel(channel_id: int) -> RequiredChannel | None:
    async with Session() as s:
        return await s.get(RequiredChannel, channel_id)


async def get_active_required_channels() -> list[RequiredChannel]:
    async with Session() as s:
        res = await s.execute(
            select(RequiredChannel)
            .where(RequiredChannel.is_active == True)  # noqa: E712
            .order_by(RequiredChannel.id.asc())
        )
        return list(res.scalars().all())


async def get_all_required_channels() -> list[RequiredChannel]:
    """Barcha majburiy kanallar (faol va nofaol) — admin ro'yxati uchun."""
    async with Session() as s:
        res = await s.execute(
            select(RequiredChannel).order_by(RequiredChannel.id.asc())
        )
        return list(res.scalars().all())


async def set_required_channel_active(channel_id: int, active: bool) -> None:
    async with Session() as s:
        await s.execute(
            update(RequiredChannel)
            .where(RequiredChannel.id == channel_id)
            .values(is_active=active)
        )
        await s.commit()


async def set_required_channel_invite_link(channel_id: int, link: str | None) -> None:
    async with Session() as s:
        await s.execute(
            update(RequiredChannel)
            .where(RequiredChannel.id == channel_id)
            .values(invite_link=link)
        )
        await s.commit()


# ---------- Qo'shimcha sozlamalar (admin panel orqali) ----------
async def get_withdraw_channel_id() -> str:
    """Yechib olish zayafkalari tashlanadigan kanal (ID '-100...' yoki @username)."""
    return await get_setting("withdraw_channel_id", "")


async def set_withdraw_channel_id(value: str) -> None:
    await set_setting("withdraw_channel_id", value)


async def get_referral_task_threshold() -> int:
    """Referal bonusi berilishi uchun referal bajarishi kerak bo'lgan zadaniyalar soni.
    Default: 3 (foydalanuvchi talabiga ko'ra)."""
    raw = await get_setting("referral_task_threshold", "")
    return int(raw) if raw.isdigit() else 3


async def set_referral_task_threshold(n: int) -> None:
    await set_setting("referral_task_threshold", str(n))


async def get_ton_uzs_rate_setting() -> float:
    """Admin tomonidan o'rnatilgan 1 TON = ? so'm kursi.
    0 (yoki o'rnatilmagan) bo'lsa jonli kursga tayanish kerakligini bildiradi."""
    raw = await get_setting("ton_uzs_rate", "")
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0


async def set_ton_uzs_rate(value: str) -> None:
    await set_setting("ton_uzs_rate", value)


# ---------- Stats (admin) ----------
async def get_stats() -> dict:
    async with Session() as s:
        users = (await s.execute(select(func.count()).select_from(User))).scalar() or 0
        orders = (await s.execute(select(func.count()).select_from(Order))).scalar() or 0
        revenue = (
            await s.execute(
                select(func.coalesce(func.sum(Order.amount), 0)).where(
                    Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERING, OrderStatus.DONE])
                )
            )
        ).scalar() or 0
        stars_sold = (
            await s.execute(
                select(func.coalesce(func.sum(Order.stars), 0)).where(
                    Order.status == OrderStatus.DONE
                )
            )
        ).scalar() or 0
        return {
            "users": users,
            "orders": orders,
            "revenue": revenue,
            "stars_sold": stars_sold,
        }
