# bot/service/noshenie_service.py
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models.players.player import Player
from bot.database.models.bets.bet import Bet
from bot.database.models.bets.enums import RarityEnum
from bot.database.models.user import User

NOSHENIE_COOLDOWN = timedelta(hours=0.1)
NOSHENIE_COST_NEURONS = 140
NEURON_REWARD_MIN = 10
NEURON_REWARD_MAX = 25
LEGENDARY_PITY_THRESHOLD = 60
BET_LEVEL_STEP = 5
MAX_BET_LEVEL = 60

BET_NAMES_BY_RARITY = {
    RarityEnum.COMMON: ["Маршл", "Тоша."],
    RarityEnum.RARE: ["Эмилия"],
    RarityEnum.EPIC: ["Аминия"],
    RarityEnum.LEGENDARY: ["Поли"],
}

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
            neurons=0,
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
                "bets_count": player.count_bets,
            }

    if player.neurons < NOSHENIE_COST_NEURONS:
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
            "neurons_spent": 0,
            "neurons_reward": 0,
            "total_neurons": player.neurons,
            "bets_count": player.count_bets,
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
    neurons_spent = NOSHENIE_COST_NEURONS

    player.neurons = player.neurons - neurons_spent + neurons_reward
    player.count_bets += 1
    player.last_noshenie_at = now

    await session.commit()
    await session.refresh(player)
    await session.refresh(bet)

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
        "neurons_spent": neurons_spent,
        "neurons_reward": neurons_reward,
        "total_neurons": player.neurons,
        "bets_count": player.count_bets,
    }
