from sqlalchemy import select, update
from bot.database.models.user import async_session
from bot.database.models.user import User
from bot.database.models.players.player import Player
from bot.database.models.bets.bet import Bet
from bot.database.models.bets.enums import RarityEnum

def extract_is_premium(tg_user):
    value = getattr(tg_user, 'is_premium', False)
    if value is None:
        return False
    return bool(value)

async def set_user(tg_user):
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_id == tg_user.id)
        )

        if not user:
            user = User(
                tg_id=tg_user.id,
                is_premium=extract_is_premium(tg_user),
                tel_number=None,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )
            session.add(user)
            await session.flush()

            player = Player(
                user_id=user.id,
                rank=0,
                xp=0,
                neurons=400,
                count_bets=1,
                noshenie_count=0,
            )
            session.add(player)
            await session.flush()

            base_bet = Bet(
                owner_id=player.id,
                rarity=RarityEnum.COMMON,
                name="Зуппа",
                level=5,
            )
            session.add(base_bet)

            await session.commit()
            print(f'> +Новый пользователь создан: {tg_user.id}')
        else:
            await session.execute(
                update(User)
                .where(User.tg_id == tg_user.id)
                .values(
                    is_premium=extract_is_premium(tg_user),
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    last_name=tg_user.last_name
                )
            )
            await session.commit()
            print(f'> ~Обновлена информация пользователя {tg_user.id}')
