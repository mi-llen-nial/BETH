from sqlalchemy import BigInteger, String, Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.sql import expression

from bot.core.config import DATABASE_URL
from bot.database.models.base import Base
from bot.database.models.promo import PromoCode, PromoRedemption  # регистрируем модели промокодов
from bot.database.models.shelter import ShelterListing, ShelterSellRequest  # регистрируем модели приюта

engine = create_async_engine(url=DATABASE_URL)
async_session = async_sessionmaker(engine)

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
    async with engine.begin() as eng:
        await eng.run_sync(Base.metadata.create_all)
