from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select, func, or_

from bot.database.models.base import async_session
from bot.database.models.merge import MergeSession
from bot.database.request.player_requests import get_or_create_player_for_user

router = Router()


@router.message(F.text == "👤Профиль")
async def __(message: Message):
    tg_id = message.from_user.id
    player = await get_or_create_player_for_user(tg_id)

    async with async_session() as session:
        merges_count = await session.scalar(
            select(func.count())
            .select_from(MergeSession)
            .where(
                MergeSession.status == "completed",
                or_(
                    MergeSession.player1_id == player.id,
                    MergeSession.player2_id == player.id,
                ),
            )
        )

    username = message.from_user.first_name or message.from_user.username or "Игрок"

    text = (
        f"Профиль {username}\n"
        "--------------------------------\n\n"
        f"👤 Ранг: <b>{player.rank}</b>\n"
        f"🫆 Нейроны: <b>{player.neurons}</b>\n"
        f"💼 Количество Бэтов: <b>{player.count_bets}</b>\n"
        f"🧬 Слияний за всё время: <b>{merges_count or 0}</b>"
    )

    await message.answer(text, parse_mode="HTML")
