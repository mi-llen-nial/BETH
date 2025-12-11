# bot/handlers/client/commands/profile.py
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select
from bot.database.models.base import async_session
from bot.database.models.players.player import Player
from bot.database.request.player_requests import get_or_create_player_for_user

router = Router()

@router.message(F.text == "👤Профиль")
async def __(message: Message):
    tg_id = message.from_user.id
    player = await get_or_create_player_for_user(tg_id)

    text = (
        f'Профиль: {message.from_user.username}\n'
        f'Ранг: {player.rank}\n'
        f'Нейроны: {player.neurons}\n'
        f'Количество Бэтов: {player.count_bets}\n'
    )

    if not player:
        await message.answer(
            'У тебя пока нет игрового профиля.\n'
            'Нажми /start и сделай первое ношение!'
        )
        return

    await message.answer(text)