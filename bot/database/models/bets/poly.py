
from bot.database.models.bets.enums import BetCode, RarityEnum
from bot.database.models.bets.bet import Bet

POLY_CONFIG = {
    'code': BetCode.POLY,
    'display_name': 'Поли',
    'description': 'Любопытный неоновый Бет, который любит слияния.',
}

def create_poly(owner_id: int, rarity: RarityEnum) -> Bet:
    return Bet(
        owner_id=owner_id,
        code=POLY_CONFIG['code'],
        name=POLY_CONFIG['display_name'],
        rarity=rarity,
    )
