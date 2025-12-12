from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.bets.bet import Bet
from bot.database.models.bets.enums import RarityEnum
from bot.database.models.players.player import Player
from bot.database.models.user import User
from bot.service.xp_service import add_xp, LAB_XP_REWARD


LAB_DURATION_MINUTES = {
    10: "10 минут",
    60: "1 час",
    360: "6 часов",
    720: "12 часов",
    1440: "24 часа",
}

# 140 нейронов за 12 часов базового фарма
BASE_REWARD_PER_MINUTE = 140 / (12 * 60)

RARITY_MULTIPLIER = {
    RarityEnum.COMMON.value: 1.0,
    RarityEnum.RARE.value: 1.3,
    RarityEnum.EPIC.value: 1.7,
    RarityEnum.LEGENDARY.value: 2.2,
}

RANK_FACTOR = 0.03
LEVEL_FACTOR = 0.005


def _calc_lab_reward(player: Player, bet: Bet, duration_minutes: int) -> int:
    base = BASE_REWARD_PER_MINUTE * duration_minutes
    rarity_mult = RARITY_MULTIPLIER.get(bet.rarity, 1.0)
    rank_mult = 1.0 + player.rank * RANK_FACTOR
    level_mult = 1.0 + (bet.level or 0) * LEVEL_FACTOR
    value = int(base * rarity_mult * rank_mult * level_mult)
    if value < int(base):
        value = int(base)
    return max(value, 1)


def calc_lab_total_reward(player: Player, bet: Bet) -> int:
    """
    Посчитать полную награду за текущую сессию лаборатории для Бета.
    Используется, например, в профиле для отображения «ожидаемых нейронов».
    """
    if not bet.in_lab or not bet.lab_started_at or not bet.lab_ends_at:
        return 0

    duration_minutes = int((bet.lab_ends_at - bet.lab_started_at).total_seconds() // 60)
    if duration_minutes <= 0:
        duration_minutes = 1

    return _calc_lab_reward(player, bet, duration_minutes)


async def _get_player_by_tg(session: AsyncSession, tg_id: int) -> Player | None:
    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if not user:
        return None
    return await session.scalar(select(Player).where(Player.user_id == user.id))


async def start_lab_for_bet(
    session: AsyncSession, tg_id: int, bet_id: int, duration_minutes: int
) -> Dict[str, Any]:
    if duration_minutes not in LAB_DURATION_MINUTES:
        return {"ok": False, "reason": "bad_duration", "message": "Некорректная длительность."}

    player = await _get_player_by_tg(session, tg_id)
    if not player:
        return {
            "ok": False,
            "reason": "player_not_found",
            "message": "Игровой профиль не найден. Сначала используй /start.",
        }

    bet = await session.scalar(
        select(Bet).where(
            Bet.id == bet_id,
            Bet.owner_id == player.id,
            Bet.is_active == True,
            Bet.in_shelter == False,
        )
    )
    if not bet:
        return {
            "ok": False,
            "reason": "bet_not_found",
            "message": "Этот Бет не найден или больше тебе не принадлежит.",
        }

    if bet.in_lab:
        return {
            "ok": False,
            "reason": "already_in_lab",
            "message": "Этот Бет уже находится в лаборатории.",
        }

    now = datetime.now(timezone.utc)
    bet.in_lab = True
    bet.lab_started_at = now
    bet.lab_ends_at = now + timedelta(minutes=duration_minutes)

    reward = _calc_lab_reward(player, bet, duration_minutes)

    await session.commit()
    await session.refresh(bet)

    return {
        "ok": True,
        "reason": None,
        "bet_id": bet.id,
        "bet_name": bet.name,
        "rarity": bet.rarity,
        "duration_minutes": duration_minutes,
        "duration_label": LAB_DURATION_MINUTES[duration_minutes],
        "expected_reward": reward,
        "lab_ends_at": bet.lab_ends_at,
    }


async def collect_lab_reward(
    session: AsyncSession, tg_id: int, bet_id: int
) -> Dict[str, Any]:
    player = await _get_player_by_tg(session, tg_id)
    if not player:
        return {
            "ok": False,
            "reason": "player_not_found",
            "message": "Игровой профиль не найден. Сначала используй /start.",
        }

    bet = await session.scalar(
        select(Bet).where(
            Bet.id == bet_id,
            Bet.owner_id == player.id,
            Bet.is_active == True,
            Bet.in_shelter == False,
        )
    )
    if not bet:
        return {
            "ok": False,
            "reason": "bet_not_found",
            "message": "Этот Бет не найден или больше тебе не принадлежит.",
        }

    if not bet.in_lab or not bet.lab_started_at or not bet.lab_ends_at:
        return {
            "ok": False,
            "reason": "not_in_lab",
            "message": "Этот Бет сейчас не в лаборатории.",
        }

    now = datetime.now(timezone.utc)
    if now < bet.lab_ends_at:
        remaining = bet.lab_ends_at - now
        minutes_left = int(remaining.total_seconds() // 60)
        return {
            "ok": False,
            "reason": "not_ready",
            "message": f"Бет ещё работает в лаборатории.\nОсталось примерно {minutes_left} минут.",
        }

    duration_minutes = int((bet.lab_ends_at - bet.lab_started_at).total_seconds() // 60)
    reward = _calc_lab_reward(player, bet, duration_minutes)

    player.neurons += reward

    # Опыт за завершение работы Бета в лаборатории
    rank_before = player.rank
    rank_ups = add_xp(player, LAB_XP_REWARD)

    bet.in_lab = False
    bet.lab_started_at = None
    bet.lab_ends_at = None

    await session.commit()
    await session.refresh(player)
    await session.refresh(bet)

    return {
        "ok": True,
        "reason": None,
        "reward": reward,
        "bet_id": bet.id,
        "bet_name": bet.name,
        "rarity": bet.rarity,
        "player_neurons": player.neurons,
        "xp_gained": LAB_XP_REWARD,
        "rank_before": rank_before,
        "rank_after": player.rank,
        "rank_ups": rank_ups,
    }
