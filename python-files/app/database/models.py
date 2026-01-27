from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import (
    Integer, String, BigInteger, ForeignKey, Boolean, 
    DateTime, Float, func, UniqueConstraint, CheckConstraint, text, Text, Index
)
from .session import engine 
from sqlalchemy import BigInteger, String, DateTime, Boolean, ForeignKey, Integer, Float, UniqueConstraint, CheckConstraint, Index, func
# --- БАЗОВЫЙ КЛАСС ---
class Base(DeclarativeBase):
    pass
# ==================================================
# 1. Наказания и чёрный список
# ==================================================

class Punishment(Base):
    __tablename__ = "punishments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), index=True)
    admin_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=True)

    action_type: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CountryBlacklist(Base):
    __tablename__ = "country_blacklist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    country_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meme_countries.country_id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    admin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))

    is_perm_ban: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)


# ==================================================
# 2. User и MemeCountry
# ==================================================

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    userfullname: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=0)

    position: Mapped[str] = mapped_column(String(50), default="Путешественник", nullable=False)
    is_ruler: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lost_in_casino: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_country_creation: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_country_deletion: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    adminlevel: Mapped[int] = mapped_column(Integer, default=0)

    country_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("meme_countries.country_id"), nullable=True)

    country_blacklisted: Mapped[List["CountryBlacklist"]] = relationship(
        "CountryBlacklist",
        foreign_keys=[CountryBlacklist.user_id],  # ← вот это спасает
        back_populates="user",
        lazy="selectin"
    )

    punishments: Mapped[List["Punishment"]] = relationship(
        "Punishment",
        foreign_keys=[Punishment.user_id],
        back_populates="user",
        lazy="selectin"
    )

    country: Mapped[Optional["MemeCountry"]] = relationship("MemeCountry", back_populates="citizens", foreign_keys=[country_id])
    ruled_country_list: Mapped[List["MemeCountry"]] = relationship("MemeCountry", back_populates="ruler", foreign_keys="MemeCountry.ruler_id")

    admin: Mapped[Optional["Admins"]] = relationship("Admins", back_populates="user", uselist=False)

    history_as_target: Mapped[List["History"]] = relationship("History", back_populates="target_user", foreign_keys="History.target_id")
    history_as_admin: Mapped[List["History"]] = relationship("History", back_populates="admin_user", foreign_keys="History.admin_id")

    reviews: Mapped[List["CountryReview"]] = relationship("CountryReview", back_populates="user")

class MemeCountry(Base):
    __tablename__ = "meme_countries"

    # ОСНОВНАЯ ИНФОРМАЦИЯ
    country_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Уникальный ID страны
    ruler_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)  # Кто правит страной
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # ИДЕНТИФИКАЦИЯ И НАЗВАНИЯ
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)  # ID Telegram чата страны
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # Официальное название страны
    memename: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # Мемное имя/шутка страны

    # ОПИСАНИЕ И ДЕТАЛИ
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # Подробное описание страны
    ideology: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Идеология/политика страны
    avatar_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Ссылка на флаг/эмблему
    position: Mapped[str] = mapped_column(String(50), default="Путешественник", nullable=False)  # Должность в стране (по умолчанию)
    map_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)  # Ссылка на карту страны
    country_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # СТАТИСТИКА И РЕЙТИНГ
    influence_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Очки влияния страны
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # Средний рейтинг страны
    total_reviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Количество отзывов

    # ЭКОНОМИКА И НАЛОГИ
    tax_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # Налоговая ставка (0.0-0.5)
    treasury: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)  # Казна страны (деньги)

    # ЧЕРНЫЙ СПИСОК
    blacklist: Mapped[List["CountryBlacklist"]] = relationship("CountryBlacklist", back_populates="country", lazy="selectin")  # Кто запрещен в стране

    # ФАЙЛЫ (ЛОКАЛЬНОЕ ХРАНЕНИЕ)
    flag_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # file_id флага в Telegram
    map_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # file_id карты в Telegram

    # СВЯЗИ С ПОЛЬЗОВАТЕЛЯМИ
    ruler: Mapped["User"] = relationship("User", back_populates="ruled_country_list", foreign_keys=[ruler_id])  # Сам правитель
    citizens: Mapped[List["User"]] = relationship("User", back_populates="country", foreign_keys="User.country_id")  # Граждане страны
    reviews: Mapped[List["CountryReview"]] = relationship("CountryReview", back_populates="country")  # Отзывы о стране


# ==================================================
# 3. Остальные модели
# ==================================================
class RPEvent(Base):
    __tablename__ = 'rp_events'
    
    event_id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey('users.user_id'))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='active')  # active, finished, cancelled
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    finished_at: Mapped[Optional[datetime]]
    
    participants = relationship("RPParticipant", back_populates="event")

class RPParticipant(Base):
    __tablename__ = 'rp_participants'
    
    participant_id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('rp_events.event_id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.user_id'))
    joined_at: Mapped[datetime] = mapped_column(default=func.now())
    
    event = relationship("RPEvent", back_populates="participants")
    user = relationship("User")

class CountryReview(Base):
    __tablename__ = "country_reviews"

    review_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    country_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meme_countries.country_id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "country_id", name="_user_country_uc"),)

    user: Mapped["User"] = relationship("User", back_populates="reviews")
    country: Mapped["MemeCountry"] = relationship("MemeCountry", back_populates="reviews")


class History(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    target_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    admin_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[admin_id], back_populates="history_as_admin")
    target_user: Mapped["User"] = relationship("User", foreign_keys=[target_id], back_populates="history_as_target")

    __table_args__ = (
        Index("ix_history_target_time", "target_id", "timestamp"),
        Index("ix_history_admin_time", "admin_id", "timestamp"),
    )


class Admins(Base):
    __tablename__ = "admins"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), primary_key=True)
    userfullname: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    adminlevel: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (CheckConstraint("adminlevel BETWEEN 0 AND 4", name="check_admin_level"),)

    user: Mapped["User"] = relationship("User", back_populates="admin", uselist=False)


class ReservedCountryNames(Base):
    __tablename__ = "reserved_country_names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    added_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


# ==================================================
# Доопределение обратных связей
# ==================================================

Punishment.user: Mapped["User"] = relationship(
    "User",
    foreign_keys=[Punishment.user_id],
    back_populates="punishments"
)
Punishment.admin: Mapped[Optional["User"]] = relationship(
    "User",
    foreign_keys=[Punishment.admin_id]
)

CountryBlacklist.country: Mapped["MemeCountry"] = relationship("MemeCountry", back_populates="blacklist")
CountryBlacklist.user: Mapped["User"] = relationship(
    "User",
    foreign_keys=[CountryBlacklist.user_id],
    back_populates="country_blacklisted"
)
CountryBlacklist.admin: Mapped["User"] = relationship(
    "User",
    foreign_keys=[CountryBlacklist.admin_id]
)

# 6) Функция для создания всех таблиц (если их нет)
async def async_main():
    async with engine.begin() as conn:
        # run_sync оборачивает синхронный create_all в асинхронный контекст
        await conn.run_sync(Base.metadata.create_all)