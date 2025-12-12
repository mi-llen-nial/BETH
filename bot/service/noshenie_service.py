# bot/service/noshenie_service.py
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.players.player import Player
from bot.database.models.bets.bet import Bet
from bot.database.models.bets.enums import RarityEnum
from bot.database.models.user import User
from bot.service.xp_service import add_xp, NOSHENIE_XP_REWARD

NOSHENIE_COOLDOWN = timedelta(hours=0.0)
NOSHENIE_COST_NEURONS = 140
NEURON_REWARD_MIN = 10
NEURON_REWARD_MAX = 25
LEGENDARY_PITY_THRESHOLD = 60
BET_LEVEL_STEP = 5
MAX_BET_LEVEL = 60

BET_NAMES_BY_RARITY = {
    RarityEnum.COMMON: ["Маршал", "Тоша", "Эмма", "Георг", "Тула", "Зоня", "Тути"],
    RarityEnum.RARE: ["Эмилия", "Сино", "Том", "Элин"],
    RarityEnum.EPIC: ["Аминия", "Тоцерк", "Крона"],
    RarityEnum.LEGENDARY: ["Поли", "Cулла"],
}


async def _get_active_bets_count(session: AsyncSession, player_id: int) -> int:
    """
    Подсчитать текущее количество Бетов, которые реально принадлежат игроку.
    Учитываем только активных Бетов (проигранные в слиянии не считаем).
    """
    value = await session.scalar(
        select(func.count())
        .select_from(Bet)
        .where(Bet.owner_id == player_id, Bet.is_active == True)
    )
    return int(value or 0)

async def get_or_create_player(session, tg_id: int) -> Player:
    user = await session.scalar(
        select(User).where(User.tg_id == tg_id)
    )

    if not user:
        raise RuntimeError(f"User с tg_id={tg_id} не найден, сначала дерни /start")


    player = await session.scalar(
        select(Player).where(Player.user_id == user.id)
    )

    if not player:
        player = Player(
            user_id=user.id,
            rank=0,
            xp=0,
            neurons=400,
            count_bets=0,
            noshenie_count=0,
        )
        session.add(player)
        await session.commit()
        await session.refresh(player)
        print(f"> +Создан новый Player для user_id={user.id}")

    return player


def roll_rarity() -> RarityEnum:
    x = random.random()

    if x < 0.80:
        return RarityEnum.COMMON
    elif x < 0.90:
        return RarityEnum.RARE
    elif x < 0.98:
        return RarityEnum.EPIC
    else:
        return RarityEnum.LEGENDARY


def roll_neuron_reward() -> int:
    return random.randint(NEURON_REWARD_MIN, NEURON_REWARD_MAX)


def roll_bet_name_for_rarity(rarity: RarityEnum) -> str:
    names = BET_NAMES_BY_RARITY[rarity]
    return random.choice(names)


async def do_noshenie(session: AsyncSession, tg_id: int) -> Dict[str, Any]:
    player = await get_or_create_player(session, tg_id)
    now = datetime.now(timezone.utc)

    if player.last_noshenie_at is not None:
        delta = now - player.last_noshenie_at
        if delta < NOSHENIE_COOLDOWN:
            remaining = NOSHENIE_COOLDOWN - delta
            minutes_left = int(remaining.total_seconds() // 60) + 1
            bets_count = await _get_active_bets_count(session, player.id)
            return {
                "ok": False,
                "reason": "cooldown",
                "remaining_minutes": minutes_left,
                "required_neurons": None,
                "current_neurons": player.neurons,
                "rarity": None,
                "bet_name": None,
                "bet_level": None,
                "is_new_bet": None,
                "neurons_spent": 0,
                "neurons_reward": 0,
                "total_neurons": player.neurons,
                "bets_count": bets_count,
                "xp_gained": 0,
                "rank": player.rank,
            }

    # Проверяем, доступно ли бесплатное ношение на сегодня
    is_free_available = (
        player.last_free_noshenie_at is None
        or player.last_free_noshenie_at.date() < now.date()
    )
    use_free = is_free_available

    # Если бесплатное уже использовано и нейронов не хватает — не даём ношение
    if not use_free and player.neurons < NOSHENIE_COST_NEURONS:
        bets_count = await _get_active_bets_count(session, player.id)
        return {
            "ok": False,
            "reason": "not_enough_neurons",
            "remaining_minutes": None,
            "required_neurons": NOSHENIE_COST_NEURONS,
            "current_neurons": player.neurons,
            "rarity": None,
            "bet_name": None,
            "bet_level": None,
            "is_new_bet": None,
            "is_free": False,
            "neurons_spent": 0,
            "neurons_reward": 0,
            "total_neurons": player.neurons,
            "bets_count": bets_count,
            "xp_gained": 0,
            "rank": player.rank,
        }

    if player.noshenie_count >= LEGENDARY_PITY_THRESHOLD - 1:
        rarity = RarityEnum.LEGENDARY
    else:
        rarity = roll_rarity()

    if rarity == RarityEnum.LEGENDARY:
        player.noshenie_count = 0
    else:
        player.noshenie_count += 1

    bet_name = roll_bet_name_for_rarity(rarity)

    existing_bet = await session.scalar(
        select(Bet).where(
            Bet.owner_id == player.id,
            Bet.name == bet_name,
            Bet.is_active == True,  # используем только активных Бетов
        )
    )

    if existing_bet is None:
        bet_level = BET_LEVEL_STEP
        bet = Bet(owner_id=player.id, rarity=rarity, name=bet_name, level=bet_level)
        session.add(bet)
        is_new_bet = True
    else:
        bet = existing_bet
        current_level = bet.level or 0
        new_level = min(current_level + BET_LEVEL_STEP, MAX_BET_LEVEL)
        bet.level = new_level
        bet_level = new_level
        is_new_bet = False

    neurons_reward = roll_neuron_reward()
    neurons_spent = 0 if use_free else NOSHENIE_COST_NEURONS

    player.neurons = player.neurons - neurons_spent + neurons_reward
    player.count_bets += 1
    player.last_noshenie_at = now

    if use_free:
        player.last_free_noshenie_at = now

    # Опыт за ношение
    xp_gained = NOSHENIE_XP_REWARD
    rank_before = player.rank
    rank_ups = add_xp(player, xp_gained)

    await session.commit()
    await session.refresh(player)
    await session.refresh(bet)

    bets_count = await _get_active_bets_count(session, player.id)

    return {
        "ok": True,
        "reason": None,
        "remaining_minutes": None,
        "required_neurons": None,
        "current_neurons": player.neurons,
        "rarity": rarity,
        "bet_name": bet_name,
        "bet_level": bet_level,
        "is_new_bet": is_new_bet,
        "is_free": use_free,
        "neurons_spent": neurons_spent,
        "neurons_reward": neurons_reward,
        "total_neurons": player.neurons,
        "bets_count": bets_count,
        "xp_gained": xp_gained,
        "rank": player.rank,
        "rank_before": rank_before,
        "rank_ups": rank_ups,
    }
