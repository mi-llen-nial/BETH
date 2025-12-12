from datetime import datetime
from sqlalchemy import Integer, String, DateTime, func, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression
from bot.database.models.base import Base


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"),
        index=True,
        nullable=True,
    )
    rarity: Mapped[str] = mapped_column(String(16))
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=5)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=expression.true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    owner: Mapped["Player"] = relationship(back_populates="bets")
