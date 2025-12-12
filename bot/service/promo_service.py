from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.promo import PromoCode, PromoRedemption
from bot.service.noshenie_service import get_or_create_player


async def redeem_promo(
    session: AsyncSession,
    tg_id: int,
    raw_code: str,
) -> Dict[str, Any]:
    """
    Активировать промокод для пользователя.
    """
    code = (raw_code or "").strip().upper()
    if not code:
        return {
            "ok": False,
            "reason": "empty",
            "message": "Нужно указать код после команды.",
        }

    promo = await session.scalar(
        select(PromoCode).where(PromoCode.code == code)
    )

    if not promo or not promo.is_active:
        return {
            "ok": False,
            "reason": "not_found",
            "message": "Такого промокода нет или он уже отключён.",
        }

    now = datetime.now(timezone.utc)
    if promo.expires_at and promo.expires_at < now:
        return {
            "ok": False,
            "reason": "expired",
            "message": "Срок действия этого промокода истёк.",
        }

    if promo.max_uses is not None and promo.used_count >= promo.max_uses:
        return {
            "ok": False,
            "reason": "limit",
            "message": "Лимит использований этого промокода уже исчерпан.",
        }

    player = await get_or_create_player(session, tg_id)

    already_used = await session.scalar(
        select(PromoRedemption).where(
            PromoRedemption.promo_id == promo.id,
            PromoRedemption.player_id == player.id,
        )
    )

    if already_used:
        return {
            "ok": False,
            "reason": "already_used",
            "message": "Ты уже использовал этот промокод.",
        }

    player.neurons += promo.reward_neurons
    promo.used_count += 1

    redemption = PromoRedemption(
        promo_id=promo.id,
        player_id=player.id,
    )
    session.add(redemption)

    await session.commit()
    await session.refresh(player)
    await session.refresh(promo)

    return {
        "ok": True,
        "reason": None,
        "code": promo.code,
        "reward": promo.reward_neurons,
        "total_neurons": player.neurons,
    }

