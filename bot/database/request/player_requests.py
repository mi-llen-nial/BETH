from sqlalchemy import select
from bot.database.models.base import async_session
from bot.database.models.user import User
from bot.database.models.players.player import Player

async def get_or_create_player_for_user(tg_id: int) -> Player:
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_id == tg_id)
        )

        if user is None:
            raise RuntimeError(
                f"User с tg_id={tg_id} не найден. "
                f"Сначала должен вызываться set_user() в /start."
            )

        player = await session.scalar(
            select(Player).where(Player.user_id == user.id)
        )

        if player is None:
            player = Player(
                user_id=user.id,
                rank=0,
                neurons=0,
                count_bets=0,
            )
            session.add(player)
            await session.commit()
            await session.refresh(player)
            print(f"> +Создан новый Player для user_id={user.id}")

        return player
    