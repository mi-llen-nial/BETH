from typing import Dict

from bot.database.models.players.player import Player

MAX_RANK = 80

FIRST_STEP_FOR_RANK1 = 100
DELTA_INCREMENT = 50

NOSHENIE_XP_REWARD = 15
MERGE_XP_REWARD = 5
LAB_XP_REWARD = 10


def _build_xp_table() -> Dict[int, int]:
    table: Dict[int, int] = {}
    table[0] = 50

    current = FIRST_STEP_FOR_RANK1
    delta = DELTA_INCREMENT
    for rank in range(1, MAX_RANK):
        table[rank] = current
        current += delta
        delta += DELTA_INCREMENT

    return table


XP_NEXT_PER_RANK: Dict[int, int] = _build_xp_table()


def get_xp_to_next_rank(rank: int) -> int | None:
    if rank >= MAX_RANK:
        return None
    return XP_NEXT_PER_RANK.get(rank)


def add_xp(player: Player, amount: int) -> int:
    if amount <= 0 or player.rank >= MAX_RANK:
        return 0

    total_rank_ups = 0

    current_xp = getattr(player, "xp", 0) or 0
    player.xp = current_xp + amount

    while player.rank < MAX_RANK:
        needed = get_xp_to_next_rank(player.rank)
        if needed is None or player.xp < needed:
            break

        player.xp -= needed
        player.rank += 1
        total_rank_ups += 1

    return total_rank_ups

