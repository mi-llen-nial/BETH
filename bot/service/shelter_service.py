from typing import Dict, Any, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.bets.bet import Bet
from bot.database.models.bets.enums import RarityEnum
from bot.database.models.players.player import Player
from bot.database.models.shelter import ShelterListing, ShelterSellRequest
from bot.database.models.user import User
from bot.service.noshenie_service import get_or_create_player


RARITY_PRICE_LIMITS: Dict[str, tuple[int, int]] = {
    RarityEnum.COMMON.value: (80, 350),
    RarityEnum.RARE.value: (120, 560),
    RarityEnum.EPIC.value: (160, 840),
    RarityEnum.LEGENDARY.value: (210, 1200),
}


RARITY_EMOJI = {
    RarityEnum.COMMON.value: "⭐️",
    RarityEnum.RARE.value: "🌟",
    RarityEnum.EPIC.value: "💫",
    RarityEnum.LEGENDARY.value: "✨",
}


def format_bet_short(bet: Bet) -> str:
    rarity = str(bet.rarity)
    emoji = RARITY_EMOJI.get(rarity, "⭐️")
    return f"{emoji}{bet.name} ур.{bet.level}"


async def get_market_listings(session: AsyncSession) -> List[Dict[str, Any]]:
    """
    Получить список активных лотов приюта в виде простых словарей,
    чтобы не триггерить ленивые загрузки у AsyncSession.
    """
    result = await session.execute(
        select(
            ShelterListing.id,
            ShelterListing.price,
            ShelterListing.seller_id,
            Bet.id.label("bet_id"),
            Bet.name,
            Bet.rarity,
            Bet.level,
        )
        .join(Bet, ShelterListing.bet_id == Bet.id)
        .where(
            ShelterListing.is_active == True,
            Bet.is_active == True,
            Bet.in_shelter == True,
        )
        .order_by(ShelterListing.created_at.desc())
    )
    rows = result.all()

    listings: List[Dict[str, Any]] = []
    for row in rows:
        listings.append(
            {
                "id": row.id,
                "price": row.price,
                "seller_id": row.seller_id,
                "bet_id": row.bet_id,
                "bet_name": row.name,
                "bet_rarity": row.rarity,
                "bet_level": row.level,
            }
        )
    return listings


async def start_sell_request(session: AsyncSession, tg_id: int, bet_id: int) -> Dict[str, Any]:
    player = await get_or_create_player(session, tg_id)

    bet = await session.scalar(
        select(Bet).where(
            Bet.id == bet_id,
            Bet.owner_id == player.id,
            Bet.is_active == True,
            Bet.in_lab == False,
            Bet.in_shelter == False,
        )
    )
    if not bet:
        return {
            "ok": False,
            "reason": "bet_not_available",
            "message": "Этот Бет недоступен для продажи.",
        }

    limits = RARITY_PRICE_LIMITS.get(bet.rarity)
    if not limits:
        return {
            "ok": False,
            "reason": "no_limits",
            "message": "Для этого Бета не заданы ограничения по цене.",
        }

    # Стираем предыдущий запрос, если был
    existing = await session.scalar(
        select(ShelterSellRequest).where(ShelterSellRequest.player_id == player.id)
    )
    if existing:
        await session.delete(existing)
        await session.flush()

    request = ShelterSellRequest(player_id=player.id, bet_id=bet.id)
    session.add(request)
    await session.commit()

    return {
        "ok": True,
        "reason": None,
        "bet": bet,
        "min_price": limits[0],
        "max_price": limits[1],
    }


async def finish_sell_request(session: AsyncSession, tg_id: int, price: int) -> Dict[str, Any]:
    player = await get_or_create_player(session, tg_id)

    request = await session.scalar(
        select(ShelterSellRequest).where(ShelterSellRequest.player_id == player.id)
    )
    if not request:
        return {
            "ok": False,
            "reason": "no_request",
            "message": "Нет активного выбора Бета для продажи.",
        }

    bet = await session.scalar(
        select(Bet).where(
            Bet.id == request.bet_id,
            Bet.owner_id == player.id,
            Bet.is_active == True,
            Bet.in_lab == False,
            Bet.in_shelter == False,
        )
    )
    if not bet:
        await session.delete(request)
        await session.commit()
        return {
            "ok": False,
            "reason": "bet_not_available",
            "message": "Этот Бет больше недоступен для продажи.",
        }

    limits = RARITY_PRICE_LIMITS.get(bet.rarity)
    if not limits:
        await session.delete(request)
        await session.commit()
        return {
            "ok": False,
            "reason": "no_limits",
            "message": "Для этого Бета не заданы ограничения по цене.",
        }

    min_price, max_price = limits
    if price < min_price or price > max_price:
        return {
            "ok": False,
            "reason": "bad_price",
            "message": (
                f"Цена должна быть от {min_price} до {max_price} нейронов "
                f"для Бета этой редкости."
            ),
        }

    # Проверяем существующий лот для этого Бета (в том числе неактивный)
    listing = await session.scalar(
        select(ShelterListing).where(ShelterListing.bet_id == bet.id)
    )
    if listing:
        # Обновляем существующий лот
        listing.seller_id = player.id
        listing.price = price
        listing.is_active = True
    else:
        # Создаём новый лот
        listing = ShelterListing(
            bet_id=bet.id,
            seller_id=player.id,
            price=price,
            is_active=True,
        )
        session.add(listing)

    bet.in_shelter = True
    await session.delete(request)
    await session.commit()
    await session.refresh(bet)
    await session.refresh(listing)

    return {
        "ok": True,
        "reason": None,
        "bet": bet,
        "price": price,
    }


async def buy_listing(
    session: AsyncSession,
    buyer_tg_id: int,
    listing_id: int,
) -> Dict[str, Any]:
    buyer = await get_or_create_player(session, buyer_tg_id)

    listing = await session.scalar(
        select(ShelterListing).where(ShelterListing.id == listing_id)
    )
    if not listing or not listing.is_active:
        return {
            "ok": False,
            "reason": "not_found",
            "message": "Этот Бет больше не продаётся.",
        }

    bet = await session.scalar(
        select(Bet).where(
            Bet.id == listing.bet_id,
            Bet.is_active == True,
            Bet.in_shelter == True,
        )
    )
    if not bet:
        listing.is_active = False
        await session.commit()
        return {
            "ok": False,
            "reason": "bet_missing",
            "message": "Этот Бет больше не доступен.",
        }

    seller = await session.scalar(
        select(Player).where(Player.id == listing.seller_id)
    )
    if not seller:
        listing.is_active = False
        await session.commit()
        return {
            "ok": False,
            "reason": "seller_missing",
            "message": "Продавец не найден.",
        }

    if seller.id == buyer.id:
        return {
            "ok": False,
            "reason": "self_buy",
            "message": "Нельзя покупать собственного Бета.",
        }

    price = listing.price
    if buyer.neurons < price:
        return {
            "ok": False,
            "reason": "not_enough_neurons",
            "message": (
                "Недостаточно нейронов для покупки.\n"
                f"Нужно {price}, у тебя сейчас {buyer.neurons}."
            ),
        }

    buyer.neurons -= price
    seller.neurons += price

    bet.owner_id = buyer.id
    bet.in_shelter = False
    listing.is_active = False

    await session.commit()
    await session.refresh(buyer)
    await session.refresh(seller)
    await session.refresh(bet)

    seller_user = await session.scalar(
        select(User).where(User.id == seller.user_id)
    )

    return {
        "ok": True,
        "reason": None,
        "bet": bet,
        "price": price,
        "buyer_neurons": buyer.neurons,
        "seller_neurons": seller.neurons,
        "seller_tg_id": seller_user.tg_id if seller_user else None,
    }
