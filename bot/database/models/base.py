import ssl

from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from bot.core.config import DATABASE_URL


def _create_engine():
    """
    Создаём движок SQLAlchemy.

    Для облачных БД вроде Neon требуется SSL, поэтому
    сразу включаем его через стандартный SSL‑контекст.
    """
    ssl_context = ssl.create_default_context()
    return create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"ssl": ssl_context},
    )


engine = _create_engine()
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass
