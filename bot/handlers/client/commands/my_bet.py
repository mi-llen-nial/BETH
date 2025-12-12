from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from bot.database.models.base import async_session
from bot.database.models.bets.bet import Bet
from bot.database.request.player_requests import get_or_create_player_for_user

router = Router()


@router.message(F.text == "🐾Мои беты")
async def my_bets_handler(message: Message):
    tg_id = message.from_user.id
    player = await get_or_create_player_for_user(tg_id)

    async with async_session() as session:
        result = await session.scalars(
            select(Bet)
            .where(Bet.owner_id == player.id, Bet.is_active == True)
            .order_by(Bet.rarity, Bet.level.desc(), Bet.created_at)
        )
        bets = result.all()

    if not bets:
        await message.answer(
            "У тебя пока нет Бэтов.\n"
            "Сделай первое ношение, чтобы получить своего первого питомца!"
        )
        return

    kb = InlineKeyboardBuilder()
    for bet in bets:
        btn_text = f"{bet.name} ({bet.rarity}) • ур. {bet.level}"
        kb.button(text=btn_text, callback_data=f"bet:{bet.id}")
    kb.adjust(1)

    await message.answer(
        "Твои Бэты:\n"
        "Нажми на Бэта, чтобы посмотреть его характеристики.",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("bet:"))
async def bet_details_callback(callback: CallbackQuery):
    tg_id = callback.from_user.id
    player = await get_or_create_player_for_user(tg_id)

    try:
        bet_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный выбор Бэта.", show_alert=True)
        return

    async with async_session() as session:
        bet = await session.scalar(
            select(Bet).where(
                Bet.id == bet_id,
                Bet.owner_id == player.id,
                Bet.is_active == True,
            )
        )

    if not bet:
        await callback.answer(
            "Этот Бэт не найден или больше недоступен.", show_alert=True
        )
        return

    created_at_str = (
        bet.created_at.strftime("%d.%m.%Y %H:%M") if bet.created_at else "неизвестно"
    )

    text = (
        f"🐾 <b>{bet.name}</b>\n"
        f"Редкость: <b>{bet.rarity}</b>\n"
        f"Уровень: <b>{bet.level}</b> / 60\n"
        f"Получен: <i>{created_at_str}</i>\n"
    )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
