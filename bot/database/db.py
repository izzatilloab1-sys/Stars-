"""Ma'lumotlar bazasi bilan ishlash funksiyalari."""
from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.database.models import (
    Base,
    Order,
    OrderStatus,
    Promocode,
    PromoUse,
    Setting,
    User,
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
    Qaytaradi: (referrer_id, bonus_amount) yoki None."""
    async with Session() as s:
        order = await s.get(Order, order_id)
        if not order:
            return None
        user = await s.get(User, order.user_id)
        if not user or user.referrer_id is None:
            return None
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
async def create_promocode(code: str, bonus_amount: int, max_uses: int) -> Promocode:
    async with Session() as s:
        promo = Promocode(code=code, bonus_amount=bonus_amount, max_uses=max_uses)
        s.add(promo)
        await s.commit()
        await s.refresh(promo)
        return promo


async def redeem_promocode(user_id: int, code: str) -> tuple[bool, str, int]:
    """Promokodni ishlatadi. Qaytaradi (ok, xabar, bonus)."""
    async with Session() as s:
        res = await s.execute(select(Promocode).where(Promocode.code == code))
        promo = res.scalar_one_or_none()
        if not promo or not promo.is_active:
            return False, "Bunday promokod topilmadi yoki faol emas.", 0
        if promo.used_count >= promo.max_uses:
            return False, "Promokod ishlatish limiti tugagan.", 0
        # foydalanuvchi oldin ishlatganmi?
        used = await s.execute(
            select(PromoUse).where(
                PromoUse.promo_id == promo.id, PromoUse.user_id == user_id
            )
        )
        if used.scalar_one_or_none():
            return False, "Siz bu promokodni allaqachon ishlatgansiz.", 0

        promo.used_count += 1
        s.add(PromoUse(promo_id=promo.id, user_id=user_id))
        await s.execute(
            update(User).where(User.id == user_id).values(balance=User.balance + promo.bonus_amount)
        )
        await s.commit()
        return True, f"Promokod qabul qilindi! +{promo.bonus_amount:,} so'm bonus.", promo.bonus_amount


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
