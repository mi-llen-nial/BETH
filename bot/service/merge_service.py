import random
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.bets.bet import Bet
from bot.database.models.bets.enums import RarityEnum
from bot.database.models.players.player import Player
from bot.service.noshenie_service import get_or_create_player

MERGE_COST_NEURONS = 180
MERGE_REWARD_MIN = 40
MERGE_REWARD_MAX = 180

RANK_WEIGHT = 0.05
LEVEL_WEIGHT = 0.1


def normalize_rarity(value: str | RarityEnum) -> RarityEnum:
    if isinstance(value, RarityEnum):
        return value

    for rarity in RarityEnum:
        if value in {rarity.value, rarity.name, f"RarityEnum.{rarity.name}"}:
            return rarity

    raise ValueError(f"Неизвестная редкость Бэта: {value!r}")


def upgrade_rarity(rarity: RarityEnum) -> RarityEnum | None:
    order = [
        RarityEnum.COMMON,
        RarityEnum.RARE,
        RarityEnum.EPIC,
        RarityEnum.LEGENDARY,
    ]
    try:
        idx = order.index(rarity)
    except ValueError:
        return None

    if idx >= len(order) - 1:
        return None
    return order[idx + 1]


def compute_weight(rank: int, level: int) -> float:
    return 1.0 + rank * RANK_WEIGHT + level * LEVEL_WEIGHT


def roll_merge_reward() -> int:
    return random.randint(MERGE_REWARD_MIN, MERGE_REWARD_MAX)


async def perform_merge(
    session: AsyncSession,
    initiator_tg_id: int,
    partner_tg_id: int,
    initiator_bet_id: int,
    partner_bet_id: int,
) -> Dict[str, Any]:
    initiator_player = await get_or_create_player(session, initiator_tg_id)
    partner_player = await get_or_create_player(session, partner_tg_id)

    if initiator_bet_id == partner_bet_id:
        return {
            "ok": False,
            "reason": "same_bet",
            "message": "Нельзя использовать один и тот же Бэт для обоих игроков.",
        }

    bets_result = await session.scalars(
        select(Bet).where(Bet.id.in_([initiator_bet_id, partner_bet_id]))
    )
    bets = {bet.id: bet for bet in bets_result}

    initiator_bet = bets.get(initiator_bet_id)
    partner_bet = bets.get(partner_bet_id)

    if not initiator_bet or not partner_bet:
        return {
            "ok": False,
            "reason": "bet_not_found",
            "message": "Один из выбранных Бэтов не найден.",
        }

    if initiator_bet.owner_id != initiator_player.id:
        return {
            "ok": False,
            "reason": "bet_owner_mismatch",
            "message": "Выбранный Бэт инициатора больше ему не принадлежит.",
        }

    if partner_bet.owner_id != partner_player.id:
        return {
            "ok": False,
            "reason": "bet_owner_mismatch",
            "message": "Выбранный Бэт второго игрока больше ему не принадлежит.",
        }

    initiator_rarity = normalize_rarity(initiator_bet.rarity)
    partner_rarity = normalize_rarity(partner_bet.rarity)

    if initiator_rarity == RarityEnum.LEGENDARY or partner_rarity == RarityEnum.LEGENDARY:
        return {
            "ok": False,
            "reason": "legendary_not_allowed",
            "message": "Легендарных Бэтов нельзя отправлять на слияние.",
        }

    if initiator_player.neurons < MERGE_COST_NEURONS or partner_player.neurons < MERGE_COST_NEURONS:
        return {
            "ok": False,
            "reason": "not_enough_neurons",
            "message": (
                f"У обоих игроков должно быть минимум {MERGE_COST_NEURONS} нейронов "
                "для слияния."
            ),
        }

    initiator_weight = compute_weight(initiator_player.rank, initiator_bet.level or 0)
    partner_weight = compute_weight(partner_player.rank, partner_bet.level or 0)
    total_weight = initiator_weight + partner_weight

    if total_weight <= 0:
        initiator_chance = 0.5
    else:
        initiator_chance = initiator_weight / total_weight

    roll = random.random()
    initiator_wins = roll < initiator_chance

    if initiator_wins:
        winner_player = initiator_player
        winner_bet = initiator_bet
        winner_rarity = initiator_rarity
        loser_player = partner_player
        loser_bet = partner_bet
        loser_rarity = partner_rarity
    else:
        winner_player = partner_player
        winner_bet = partner_bet
        winner_rarity = partner_rarity
        loser_player = initiator_player
        loser_bet = initiator_bet
        loser_rarity = initiator_rarity

    upgraded_rarity = upgrade_rarity(winner_rarity)
    if upgraded_rarity is None:
        return {
            "ok": False,
            "reason": "cannot_upgrade",
            "message": "Редкость этого Бэта нельзя повысить.",
        }

    winner_player.neurons -= MERGE_COST_NEURONS
    loser_player.neurons -= MERGE_COST_NEURONS

    reward = roll_merge_reward()
    winner_neurons_gain = reward
    loser_neurons_gain = reward * 2

    winner_player.neurons += winner_neurons_gain
    loser_player.neurons += loser_neurons_gain

    winner_bet.rarity = upgraded_rarity.value
    loser_bet.is_active = False

    await session.commit()
    await session.refresh(winner_player)
    await session.refresh(loser_player)
    await session.refresh(winner_bet)

    return {
        "ok": True,
        "reason": None,
        "winner_tg_id": winner_player.user.tg_id,
        "loser_tg_id": loser_player.user.tg_id,
        "winner_bet_id": winner_bet.id,
        "loser_bet_id": loser_bet.id,
        "winner_bet_name": winner_bet.name,
        "winner_old_rarity": winner_rarity,
        "winner_new_rarity": upgraded_rarity,
        "loser_bet_name": loser_bet.name,
        "loser_old_rarity": loser_rarity,
        "merge_cost": MERGE_COST_NEURONS,
        "winner_neurons_gain": winner_neurons_gain,
        "loser_neurons_gain": loser_neurons_gain,
        "winner_total_neurons": winner_player.neurons,
        "loser_total_neurons": loser_player.neurons,
    }
