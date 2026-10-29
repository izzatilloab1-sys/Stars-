"""SQLAlchemy modellari."""
from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    Boolean,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OrderStatus(str, enum.Enum):
    PENDING = "pending"        # yaratildi, to'lov kutilmoqda
    PAID = "paid"              # to'landi, yetkazish kutilmoqda
    DELIVERING = "delivering"  # Fragment orqali yuborilmoqda
    DONE = "done"              # yetkazildi
    FAILED = "failed"          # xatolik
    REFUNDED = "refunded"      # qaytarildi


class WithdrawalStatus(str, enum.Enum):
    PENDING = "pending"        # zayafka yaratildi, admin tasdiqini kutmoqda
    PAID = "paid"              # admin qo'lda Stars tashladi (to'landi)
    CANCELLED = "cancelled"    # bekor qilindi, Stars balansga qaytarildi


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram id
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)  # bonus balans (so'm)
    stars_balance: Mapped[int] = mapped_column(Integer, default=0)  # bonus balans (Stars)
    referrer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    # referal (bu foydalanuvchi) zadaniya chegarasini bajargach, uni taklif qilgan
    # odamga bonus berilganini belgilovchi bayroq (ikki marta bonusdan himoya).
    ref_bonus_given: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    orders: Mapped[list["Order"]] = relationship(
        back_populates="user", foreign_keys="Order.user_id"
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    target_username: Mapped[str] = mapped_column(String(64))  # kimga yuboriladi
    stars: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)  # to'lanadigan summa (so'm)
    bonus_used: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING
    )
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pay_comment: Mapped[str | None] = mapped_column(String(64), nullable=True)  # TON memo
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="orders", foreign_keys=[user_id])


class Promocode(Base):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    bonus_amount: Mapped[int] = mapped_column(Integer)  # beriladigan bonus (so'm)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class PromoUse(Base):
    """Har bir foydalanuvchi promokodni bir marta ishlatishi uchun."""
    __tablename__ = "promo_uses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promo_id: Mapped[int] = mapped_column(Integer, ForeignKey("promocodes.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))


class Setting(Base):
    """Admin panel orqali o'zgartiriladigan sozlamalar (key-value).
    Bu yerda Fragment cookie'lari va hamyon seed'i ham saqlanadi.
    Bu .env dagi qiymatlardan USTUN turadi (bo'sh bo'lmasa)."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(2048), default="")


class Topup(Base):
    """Balans to'ldirish operatsiyasi."""
    __tablename__ = "topups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)  # so'm
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING)
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pay_comment: Mapped[str | None] = mapped_column(String(64), nullable=True)  # TON memo
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Withdrawal(Base):
    """Stars yechib olish zayafkasi (so'rovi).
    Yaratilganda stars User.stars_balance'dan ushlab qolinadi (hold).
    Admin qo'lda Stars tashlaydi -> PAID, yoki bekor qiladi -> CANCELLED (qaytariladi)."""
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    stars: Mapped[int] = mapped_column(Integer)  # yechib olinadigan Stars (15/25/50)
    status: Mapped[WithdrawalStatus] = mapped_column(
        Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Task(Base):
    """Stars ishlash uchun reklama kanali (obuna bo'lib Stars olinadi)."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(128))  # '-100...' yoki @username (getChatMember)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reward_stars: Mapped[int] = mapped_column(Integer)  # shu zadaniya uchun beriladigan Stars
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TaskCompletion(Base):
    """Har bir (zadaniya, foydalanuvchi) uchun bitta qator — takroriy to'lovning oldini oladi.

    (task_id, user_id) uchun UNIQUE cheklovi bir vaqtda kelgan ikkita 'task:check'
    bosilishi ikki marta hisob-kitob qilishiga yo'l qo'ymaydi (poyga sharoitida
    ikkinchi INSERT IntegrityError bilan tushadi)."""
    __tablename__ = "task_completions"
    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_task_completion_task_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))


class RequiredChannel(Base):
    """Majburiy obuna kaneli. invite_link — bot createChatInviteLink orqali
    yaratgan UNIKAL link (obunalarni aniqlash/hisoblash uchun)."""
    __tablename__ = "required_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(128))  # '-100...' yoki @username (getChatMember)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
