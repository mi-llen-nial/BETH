from sqlalchemy import select
from bot.database.models.user import User
from bot.database.models.players.player import Player
from bot.database.models.base import async_session


async def get_or_create_player_for_user(tg_id: int) -> Player:
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_id == tg_id)
        )
        if not user:
            raise RuntimeError(f"User с tg_id={tg_id} не найден")

        player = await session.scalar(
            select(Player).where(Player.user_id == user.id)
        )
        if not player:
            player = Player(
                user_id=user.id,
                rank=0,
                neurons=0,
            )
            session.add(player)
            await session.commit()
            await session.refresh(player)
            print(f"> +Создан новый Player для user_id={user.id}")

        return player