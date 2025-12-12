from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select, func, or_

from bot.database.models.base import async_session
from bot.database.models.merge import MergeSession
from bot.database.models.bets.bet import Bet
from bot.database.request.player_requests import get_or_create_player_for_user
from bot.service.lab_service import calc_lab_total_reward
from bot.service.xp_service import get_xp_to_next_rank

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

        active_bets_count = await session.scalar(
            select(func.count())
            .select_from(Bet)
            .where(Bet.owner_id == player.id, Bet.is_active == True)
        )

        lab_bets_result = await session.scalars(
            select(Bet).where(
                Bet.owner_id == player.id,
                Bet.is_active == True,
                Bet.in_lab == True,
            )
        )
        lab_bets = lab_bets_result.all()

    now = datetime.now(timezone.utc)
    is_free_available = (
        player.last_free_noshenie_at is None
        or player.last_free_noshenie_at.date() < now.date()
    )

    if is_free_available:
        free_line = "Доступно бесплатное ношение 🤲🏻"
    else:
        # Следующее бесплатное ношение станет доступно в начале следующего дня (UTC)
        tomorrow = datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            tzinfo=now.tzinfo,
        ) + timedelta(days=1)
        remaining = tomorrow - now
        hours_left = int(remaining.total_seconds() // 3600)
        if hours_left <= 0:
            text_time = "менее часа"
        else:
            text_time = f"{hours_left} ч."

        free_line = f"Бесплатное ношение доступно через: {text_time}"

    lab_count = len(lab_bets)
    total_lab_reward = sum(calc_lab_total_reward(player, bet) for bet in lab_bets)
    active_bets_count = int(active_bets_count or 0)

    current_rank = player.rank
    current_xp = getattr(player, "xp", 0) or 0
    xp_to_next = get_xp_to_next_rank(current_rank)

    if xp_to_next is None:
        rank_line = f"🧩Ранг: <b>{current_rank}</b> (макс.)"
    else:
        rank_line = f"🧩Ранг: <b>{current_rank}</b> ({current_xp}/{xp_to_next})"

    if lab_count > 0:
        lab_line = (
            f"🧪 В лаборатории: <b>{lab_count}</b> Бет(а)\n"
            f"⚗️ Ожидается из лаборатории: <b>{total_lab_reward}</b> нейронов"
        )
    else:
        lab_line = "🧪 В лаборатории сейчас нет Бетов"

    username = message.from_user.first_name or message.from_user.username or "Игрок"

    text = (
        f"👤 <b>Профиль {username}</b>\n"
        "--------------------------------\n\n"
        f"{rank_line}\n"
        f"🫆 Нейроны: <b>{player.neurons}</b>\n"
        f"💼 Количество Бетов: <b>{active_bets_count}</b>\n"
        f"🧬 Слияний за всё время: <b>{merges_count or 0}</b>\n\n"
        f"{lab_line}\n\n"
        f"{free_line}"
    )

    await message.answer(text, parse_mode="HTML")
