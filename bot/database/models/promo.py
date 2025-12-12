from datetime import datetime

from sqlalchemy import Integer, String, DateTime, func, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base import Base


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    reward_neurons: Mapped[int] = mapped_column(Integer, nullable=False)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    redemptions: Mapped[list["PromoRedemption"]] = relationship(
        "PromoRedemption",
        back_populates="promo",
        cascade="all, delete-orphan",
    )


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    promo_id: Mapped[int] = mapped_column(
        ForeignKey("promo_codes.id"),
        index=True,
        nullable=False,
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"),
        index=True,
        nullable=False,
    )
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    promo: Mapped["PromoCode"] = relationship(
        "PromoCode",
        back_populates="redemptions",
    )
    player: Mapped["Player"] = relationship("Player")
