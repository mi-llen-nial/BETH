from datetime import datetime

from sqlalchemy import (
    Integer,
    ForeignKey,
    DateTime,
    Boolean,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base import Base


class ShelterListing(Base):
    __tablename__ = "shelter_listings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bet_id: Mapped[int] = mapped_column(
        ForeignKey("bets.id"),
        unique=True,
        index=True,
        nullable=False,
    )
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"),
        index=True,
        nullable=False,
    )
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    bet: Mapped["Bet"] = relationship("Bet")
    seller: Mapped["Player"] = relationship("Player")


class ShelterSellRequest(Base):
    """
    Простая таблица-состояние: хранит, для какого Бета
    продавец сейчас вводит цену.
    """

    __tablename__ = "shelter_sell_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"),
        index=True,
        unique=True,
        nullable=False,
    )
    bet_id: Mapped[int] = mapped_column(
        ForeignKey("bets.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
