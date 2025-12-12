from datetime import datetime

from sqlalchemy import Integer, DateTime, func, ForeignKey, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base import Base


class MergeSession(Base):
    __tablename__ = "merge_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player1_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    player2_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"), nullable=True, index=True
    )
    player1_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    player2_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    player1_bet_id: Mapped[int | None] = mapped_column(
        ForeignKey("bets.id"), nullable=True
    )
    player2_bet_id: Mapped[int | None] = mapped_column(
        ForeignKey("bets.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="waiting", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    player1: Mapped["Player"] = relationship(
        "Player", foreign_keys=[player1_id], lazy="joined"
    )
    player2: Mapped["Player"] = relationship(
        "Player", foreign_keys=[player2_id], lazy="joined"
    )
    bet1: Mapped["Bet"] = relationship("Bet", foreign_keys=[player1_bet_id])
    bet2: Mapped["Bet"] = relationship("Bet", foreign_keys=[player2_bet_id])

