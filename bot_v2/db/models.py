from datetime import datetime, date
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot_v2.db.base import Base


class User(Base):
    """Telegram-пользователь. Создаётся при первом /start."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram_id
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    username: Mapped[str | None] = mapped_column(String(128))
    is_female: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    email: Mapped[str | None] = mapped_column(String(256))
    phone: Mapped[str | None] = mapped_column(String(32))
    occupation: Mapped[str | None] = mapped_column(String(64))  # entrepreneur / employee / student / freelance
    age: Mapped[str | None] = mapped_column(String(8))
    source: Mapped[str | None] = mapped_column(String(64))      # maps / social / internet / etc.
    pd_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # relations
    participant: Mapped["Participant | None"] = relationship(back_populates="user", uselist=False)
    diag_results: Mapped[list["DiagResult"]] = relationship(back_populates="user", order_by="DiagResult.created_at")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user", order_by="Payment.created_at")
    muhasaba_logs: Mapped[list["MuhasabaLog"]] = relationship(back_populates="user", order_by="MuhasabaLog.created_at")
    week_acks: Mapped[list["WeekAck"]] = relationship(back_populates="user")
    tracker_records: Mapped[list["TrackerRecord"]] = relationship(back_populates="user")
    wheel_records: Mapped[list["WheelRecord"]] = relationship(back_populates="user", order_by="WheelRecord.created_at")


class Participant(Base):
    """Активный участник программы. Создаётся при активации куратором."""
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)
    level: Mapped[str] = mapped_column(String(4), nullable=False)        # А / Б / В / Г
    week: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    vakt_level: Mapped[str | None] = mapped_column(String(4))             # для ВАКТ: А/Б/В
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    graduated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="participant")


class DiagResult(Base):
    """Результат диагностического теста."""
    __tablename__ = "diag_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    scores: Mapped[list[int]] = mapped_column(JSONB, nullable=False)    # [0,2,1,3,2,1,0,2]
    level_key: Mapped[str] = mapped_column(String(4), nullable=False)   # А / Б / В
    pct: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="diag_results")


class Payment(Base):
    """Платёж через ЮKassa или Telegram Payments."""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    tariff_id: Mapped[str] = mapped_column(String(32), nullable=False)  # vakt / s1_full / s3_full / jamaat / leader
    amount: Mapped[int] = mapped_column(Integer, nullable=False)         # в рублях
    yoo_payment_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    tg_charge_id: Mapped[str | None] = mapped_column(String(128))       # Telegram payment charge_id
    email_used: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending / paid / failed / refunded
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="payments")


class MuhasabaLog(Base):
    """Вечерняя мухасаба (3 вопроса самооценки)."""
    __tablename__ = "muhasaba_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    answers: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)   # [{q, a}, ...]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="muhasaba_logs")


class WeekAck(Base):
    """Факт выполнения недели участником."""
    __tablename__ = "week_acks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    level: Mapped[str] = mapped_column(String(4), nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    acked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "level", "week", name="uq_week_ack"),)

    user: Mapped["User"] = relationship(back_populates="week_acks")


class Pair(Base):
    """Якорная пара (брат/сестра в программе)."""
    __tablename__ = "pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid1: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    uid2: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    paired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dissolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("uid1", "uid2", name="uq_pair"),)


class LessonMedia(Base):
    """Видео/аудио к уроку, загружаемые куратором."""
    __tablename__ = "lesson_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(4), nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(8), nullable=False)  # video / audio
    value: Mapped[str] = mapped_column(Text, nullable=False)             # file_id или URL
    set_by: Mapped[int | None] = mapped_column(BigInteger)
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("level", "week", "media_type", name="uq_lesson_media"),)


class TrackerRecord(Base):
    """Ежедневный трекер привычек из Mini App."""
    __tablename__ = "tracker_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    habits: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # habits format: {"namaz": {"fajr": true, ...}, "daily": {"azkar": true, ...}, "weekly": {...}}
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_tracker_day"),)

    user: Mapped["User"] = relationship(back_populates="tracker_records")


class WheelRecord(Base):
    """Колесо баланса — оценка 8 сфер жизни."""
    __tablename__ = "wheel_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    scores: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)
    # {"iman": 7, "time": 5, "habits": 6, "family": 8, "health": 6, "finance": 4, "mission": 3, "social": 5}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="wheel_records")


class BotSetting(Base):
    """Настройки бота (call_link, friday_guest и т.д.)."""
    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
