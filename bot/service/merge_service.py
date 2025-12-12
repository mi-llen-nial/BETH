import random
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.bets.bet import Bet
from bot.database.models.bets.enums import RarityEnum
from bot.database.models.players.player import Player
from bot.service.noshenie_service import get_or_create_player, MAX_BET_LEVEL
from bot.service.xp_service import add_xp, MERGE_XP_REWARD

MERGE_COST_NEURONS = 80
MERGE_REWARD_MIN = 40
MERGE_REWARD_MAX = 180

RANK_WEIGHT = 0.05
LEVEL_WEIGHT = 0.1

# Насколько вклад уровня проигравшего Бета
# влияет на рост уровня победителя в зависимости от редкости.
RARITY_LEVEL_FACTOR = {
    RarityEnum.COMMON: 0.08,
    RarityEnum.RARE: 0.10,
    RarityEnum.EPIC: 0.12,
    RarityEnum.LEGENDARY: 0.15,
}

# Дополнительные множители, если проигравший Бет — легендарный.
UNDERDOG_MULTIPLIER_VS_LEGENDARY = {
    RarityEnum.COMMON: 2.0,      # обычный выиграл легу
    RarityEnum.RARE: 1.6,        # редкий выиграл легу
    RarityEnum.EPIC: 1.4,        # эпический выиграл легу
    RarityEnum.LEGENDARY: 1.0,   # лега против леги
}


def normalize_rarity(value: str | RarityEnum) -> RarityEnum:
    if isinstance(value, RarityEnum):
        return value

    for rarity in RarityEnum:
        if value in {rarity.value, rarity.name, f"RarityEnum.{rarity.name}"}:
            return rarity

    raise ValueError(f"Неизвестная редкость Бета: {value!r}")


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
            "message": "Нельзя использовать один и тот же Бет для обоих игроков.",
        }

    bets_result = await session.scalars(
        select(Bet).where(Bet.id.in_([initiator_bet_id, partner_bet_id]))
    )
    bets = {bet.id: bet for bet in bets_result}

    initiator_bet = bets.get(initiator_bet_id)
    partner_bet = bets.get(partner_bet_id)

    # Беты должны существовать и быть активными
    if (
        not initiator_bet
        or not partner_bet
        or not initiator_bet.is_active
        or not partner_bet.is_active
    ):
        return {
            "ok": False,
            "reason": "bet_not_found",
            "message": "Один из выбранных Бетов не найден или больше недоступен.",
        }

    # На всякий случай не даём сливать Бетов, которые находятся в лаборатории
    if initiator_bet.in_lab or partner_bet.in_lab:
        return {
            "ok": False,
            "reason": "bet_in_lab",
            "message": "Беты, находящиеся в лаборатории, нельзя отправлять на слияние.",
        }

    if initiator_bet.owner_id != initiator_player.id:
        return {
            "ok": False,
            "reason": "bet_owner_mismatch",
            "message": "Выбранный Бет инициатора больше ему не принадлежит.",
        }

    if partner_bet.owner_id != partner_player.id:
        return {
            "ok": False,
            "reason": "bet_owner_mismatch",
            "message": "Выбранный Бет второго игрока больше ему не принадлежит.",
        }

    initiator_rarity = normalize_rarity(initiator_bet.rarity)
    partner_rarity = normalize_rarity(partner_bet.rarity)

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

    # Считаем, на сколько уровней вырастет Бет-победитель.
    loser_level = loser_bet.level or 0
    rarity_factor = RARITY_LEVEL_FACTOR.get(loser_rarity, 0.1)
    base_gain = max(1, int(round(loser_level * rarity_factor)))

    multiplier = 1.0
    if loser_rarity == RarityEnum.LEGENDARY:
        multiplier = UNDERDOG_MULTIPLIER_VS_LEGENDARY.get(winner_rarity, 1.0)

    level_gain = max(1, int(round(base_gain * multiplier)))
    winner_old_level = winner_bet.level or 0
    winner_new_level = min(winner_old_level + level_gain, MAX_BET_LEVEL)

    winner_player.neurons -= MERGE_COST_NEURONS
    loser_player.neurons -= MERGE_COST_NEURONS

    reward = roll_merge_reward()
    winner_neurons_gain = reward
    loser_neurons_gain = reward * 2

    winner_player.neurons += winner_neurons_gain
    loser_player.neurons += loser_neurons_gain

    winner_bet.level = winner_new_level
    loser_bet.is_active = False

    # Опыт за участие в слиянии — обоим игрокам
    winner_rank_before = winner_player.rank
    loser_rank_before = loser_player.rank

    winner_rank_ups = add_xp(winner_player, MERGE_XP_REWARD)
    loser_rank_ups = add_xp(loser_player, MERGE_XP_REWARD)

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
        "winner_old_level": winner_old_level,
        "winner_new_level": winner_new_level,
        "loser_bet_name": loser_bet.name,
        "loser_level": loser_level,
        "winner_rarity": winner_rarity,
        "loser_rarity": loser_rarity,
        "level_gain": winner_new_level - winner_old_level,
        "merge_cost": MERGE_COST_NEURONS,
        "winner_neurons_gain": winner_neurons_gain,
        "loser_neurons_gain": loser_neurons_gain,
        "winner_total_neurons": winner_player.neurons,
        "loser_total_neurons": loser_player.neurons,
        "winner_xp_gained": MERGE_XP_REWARD,
        "loser_xp_gained": MERGE_XP_REWARD,
        "winner_rank_before": winner_rank_before,
        "winner_rank_after": winner_player.rank,
        "winner_rank_ups": winner_rank_ups,
        "loser_rank_before": loser_rank_before,
        "loser_rank_after": loser_player.rank,
        "loser_rank_ups": loser_rank_ups,
    }
