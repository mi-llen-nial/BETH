from sqlalchemy import BigInteger, String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression

from bot.database.models.base import Base, engine
from bot.database.models.promo import PromoCode, PromoRedemption  # регистрируем модели промокодов
from bot.database.models.shelter import ShelterListing, ShelterSellRequest  # регистрируем модели приюта

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    is_premium: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=expression.false()
    )
    tel_number: Mapped[str] = mapped_column(String(24), nullable=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    player: Mapped['Player'] = relationship(back_populates='user', uselist=False)

async def async_main():
    """
    Инициализация схемы БД.

    Используем общий engine из bot.database.models.base,
    чтобы во всех местах были одинаковые настройки подключения (в том числе SSL).
    """
    async with engine.begin() as eng:
        await eng.run_sync(Base.metadata.create_all)
