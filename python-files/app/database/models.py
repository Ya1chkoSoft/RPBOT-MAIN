from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import (
    Integer, String, BigInteger, ForeignKey, Boolean, 
    DateTime, Float, func, UniqueConstraint, CheckConstraint, text, Index
)
# Предполагаем, что session.py находится в том же пакете
from .session import engine 

# --- БАЗОВЫЙ КЛАСС ---
class Base(DeclarativeBase):
    pass

# --- 2. МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ (User) ---
class User(Base):
    __tablename__ = 'users'
    
    # --- ОСНОВНЫЕ АТРИБУТЫ ---
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    userfullname: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    
    # Должность пользователя в стране (Гражданин, Правитель, Путешественник и т.д.)
    position: Mapped[str] = mapped_column(String(50), default="Путешественник", nullable=False)
    is_ruler: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # --- КУЛДАУНЫ И АДМИН ПРАВА ---
    last_country_creation: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_country_deletion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    adminlevel: Mapped[int] = mapped_column(Integer, default=0)
    
    # FOREIGN KEY: Страна, в которой состоит пользователь (Many-to-One)
    country_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('meme_countries.country_id'), nullable=True)
    
    # -----------------------------------
    # СВЯЗИ (RELATIONSHIPS)
    # -----------------------------------
    
    # 1. Страна (Many-to-One): Страна, в которой состоит пользователь
    country: Mapped[Optional["MemeCountry"]] = relationship(
        back_populates="citizens", 
        foreign_keys="User.country_id",
    )
    
    # 2. Список стран (One-to-Many): Список стран, которыми пользователь правит
    ruled_country_list: Mapped[List["MemeCountry"]] = relationship(
        back_populates="ruler",
        foreign_keys="MemeCountry.ruler_id", # Привязка к полю ruler_id в MemeCountry
    )
    
    # 3. Администратор (One-to-One): Связь с таблицей Admins
    admin: Mapped[Optional["Admins"]] = relationship(
        "Admins", 
        back_populates="user", 
        uselist=False
    )

    # 4. История Цели (One-to-Many): История событий, где юзер — Цель
    history_as_target: Mapped[List["History"]] = relationship(
        back_populates="target_user", 
        foreign_keys="History.target_id" 
    )
    
    # 5. История Администратора (One-to-Many): История событий, инициированных этим юзером
    history_as_admin: Mapped[List["History"]] = relationship(
        back_populates="admin_user", 
        foreign_keys="History.admin_id" 
    )
    
    # 6. Отзывы (One-to-Many): Отзывы, написанные этим пользователем
    reviews: Mapped[List["CountryReview"]] = relationship(
        "CountryReview", 
        back_populates="user"
    )


# --- 1. МОДЕЛЬ СТРАНЫ (MemeCountry) ---
class MemeCountry(Base):
    __tablename__ = 'meme_countries'
    
    # Колонки
    country_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    
    # FK к пользователю, который создал и правит страной (Many-to-One)
    ruler_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    memename: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    ideology: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    position: Mapped[str] = mapped_column(String(50), default="Путешественник", nullable=False)
    map_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    
    # Поля для Рейтинга/Топа
    influence_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Связи:
    
    # 1. Правитель (Один User) - Связь Many-to-One
    ruler: Mapped["User"] = relationship(
        back_populates="ruled_country_list", # Обратная связь к списку стран в User
        foreign_keys=[ruler_id] # Явно указываем, что это наш FK
    )
    
    # 2. Граждане (Множество User) - Связь One-to-Many
    citizens: Mapped[List["User"]] = relationship(
        "User", 
        back_populates="country",
        foreign_keys="User.country_id" 
    )

    # 3. Отзывы (Множество Review)
    reviews: Mapped[List["CountryReview"]] = relationship(
        "CountryReview", 
        back_populates="country"
    )

# --- 3. МОДЕЛЬ ОТЗЫВОВ (CountryReview) ---
class CountryReview(Base):
    __tablename__ = 'country_reviews'
    
    review_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    country_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('meme_countries.country_id'), nullable=False)
    
    rating: Mapped[int] = mapped_column(Integer, nullable=False) 
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now()) 
    
    # Уникальность: 1 юзер = 1 отзыв на страну
    __table_args__ = (
        UniqueConstraint('user_id', 'country_id', name='_user_country_uc'),
    )

    user: Mapped["User"] = relationship("User", back_populates="reviews")
    country: Mapped["MemeCountry"] = relationship("MemeCountry", back_populates="reviews")


# --- 4. МОДЕЛЬ ИСТОРИИ (History) ---
class History(Base):
    __tablename__ = 'history'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    admin_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey('users.user_id'),
        nullable=True
    )

    target_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('users.user_id'),
        nullable=False
    )

    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True
    )

    points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    reason: Mapped[str] = mapped_column(
        String(512),
        nullable=False
    )

    timestamp: Mapped[DateTime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    admin_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[admin_id],
        back_populates="history_as_admin"
    )

    target_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[target_id],
        back_populates="history_as_target"
    )

    __table_args__ = (
        Index("ix_history_target_time", "target_id", "timestamp"),
        Index("ix_history_admin_time", "admin_id", "timestamp"),
    )

# --- 5. МОДЕЛЬ АДМИНОВ (Admins) ---
class Admins(Base):
    __tablename__ = 'admins'
    
    # FK и Primary Key
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id'), primary_key=True)
    userfullname: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    adminlevel: Mapped[int] = mapped_column(Integer, nullable=False)
    
    __table_args__ = (
        CheckConstraint('adminlevel BETWEEN 0 AND 4', name='check_admin_level'),
    )

    # Связь с таблицей User (One-to-One)
    user: Mapped["User"] = relationship("User", back_populates="admin", uselist=False)

#Зарезервированные страны
class ReservedCountryNames(Base):
    __tablename__ = 'reserved_country_names'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    added_by: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id'))
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

# 6) Функция для создания всех таблиц (если их нет)
async def async_main():
    async with engine.begin() as conn:
        # run_sync оборачивает синхронный create_all в асинхронный контекст
        await conn.run_sync(Base.metadata.create_all)