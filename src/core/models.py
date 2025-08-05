# models.py
import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean, Time, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.core.database import Base
from datetime import datetime


class Role(str, enum.Enum):
    ADMIN = 'admin'
    MANAGER = 'manager'
    BARISTA = 'barista'
    USER = 'user'

class SlotStatus(str, enum.Enum): # Добавим статус для слотов
    AVAILABLE = 'available'      # Доступен для бронирования
    BOOKED = 'booked'            # Забронирован
    CONFIRMED = 'confirmed'      # Бариста подтвердил выход
    COMPLETED = 'completed'      # Слот завершен
    CANCELED = 'canceled'        # Отменен

class RegistrationStatus(str, enum.Enum): # Статус регистрации пользователя
    PENDING = 'pending'     # Ожидает подтверждения
    APPROVED = 'approved'   # Одобрен
    REJECTED = 'rejected'   # Отклонен

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class User(TimestampMixin, Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    surname = Column(String, nullable=True)
    phone = Column(String, unique=True, nullable=True)
    role = Column(Enum(Role), default=Role.BARISTA)
    password = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    registration_status = Column(Enum(RegistrationStatus), default=RegistrationStatus.PENDING)
    cafe_id = Column(Integer, ForeignKey('cafes.id'), nullable=True)

    # Связи
    cafe = relationship("Cafe", back_populates="baristas", foreign_keys=[cafe_id])
    slots = relationship("Slot", back_populates="barista")

    def __repr__(self):
        return f"<User(telegram_id='{self.telegram_id}', name='{self.name}', role='{self.role}')>"

class Cafe(TimestampMixin, Base):
    __tablename__ = 'cafes'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)
    phone_number = Column(String)
    description = Column(String)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    baristas = relationship("User", back_populates="cafe", foreign_keys="User.cafe_id")
    slots = relationship("Slot", back_populates="cafe")
    manager = relationship("User", foreign_keys=[manager_id])

    def __repr__(self):
        return f"<Cafe(id={self.id}, name='{self.name}')>"


class Slot(TimestampMixin, Base):
    __tablename__ = 'slots'

    id = Column(Integer, primary_key=True, index=True)
    cafe_id = Column(Integer, ForeignKey('cafes.id'))
    barista_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    start_time = Column(DateTime, index=True)
    end_time = Column(DateTime, index=True)
    status = Column(Enum(SlotStatus), default=SlotStatus.AVAILABLE)

    # Связи
    cafe = relationship('Cafe', back_populates='slots')
    barista = relationship('User', back_populates='slots')

    def __repr__(self):
        return f"<Slot(id={self.id}, cafe_id={self.cafe_id}, barista_id={self.barista_id}, status={self.status})>"
