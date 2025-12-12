from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select

from bot.core.loader import bot
from bot.database.models.base import async_session
from bot.database.models.bets.bet import Bet
from bot.database.models.players.player import Player
from bot.database.models.user import User
from bot.service.noshenie_service import get_or_create_player
from bot.service.shelter_service import (
    get_market_listings,
    format_bet_short,
    start_sell_request,
    finish_sell_request,
    buy_listing,
)

router = Router()


SHELTER_PAGE_SIZE = 15

RARITY_EMOJI = {
    "Обычный": "⭐️",
    "Редкий": "🌟",
    "Эпический": "💫",
    "Легендарный": "✨",
}


def _format_listing_row(idx: int, item: dict) -> str:
    rarity = str(item["bet_rarity"])
    emoji = RARITY_EMOJI.get(rarity, "⭐️")
    name = item["bet_name"]
    level = item["bet_level"]
    price = item["price"]
    return f"{idx}. {emoji}{name} ур.{level} —— {price}🧬"


def _build_shelter_view(listings: list[dict], page: int) -> tuple[str, InlineKeyboardBuilder]:
    total = len(listings)
    if total == 0:
        lines = [
            "🏯 <b>Приют Бетов</b>\n",
            "Пока что в приюте нет Бетов на продажу.",
        ]
        kb = InlineKeyboardBuilder()
        kb.button(text="Купить", callback_data="shelter:buy")
        kb.button(text="Продать", callback_data="shelter:sell")
        kb.adjust(2)
        return "\n".join(lines), kb

    max_page = (total - 1) // SHELTER_PAGE_SIZE
    if page < 0:
        page = 0
    if page > max_page:
        page = max_page

    start_idx = page * SHELTER_PAGE_SIZE
    end_idx = start_idx + SHELTER_PAGE_SIZE
    page_items = listings[start_idx:end_idx]

    lines = ["🏯 <b>Приют Бетов</b>\n", "Сейчас на рынке:"]
    for offset, item in enumerate(page_items, start=1):
        idx = start_idx + offset
        lines.append(_format_listing_row(idx, item))

    lines.append(f"\nСтраница {page + 1} из {max_page + 1}")

    kb = InlineKeyboardBuilder()
    kb.button(text="Купить", callback_data="shelter:buy")
    kb.button(text="Продать", callback_data="shelter:sell")

    # Навигация по страницам
    if page > 0:
        kb.button(text="<<", callback_data=f"shelter:page:{page - 1}")
    if page < max_page:
        kb.button(text=">>", callback_data=f"shelter:page:{page + 1}")

    kb.adjust(2)
    return "\n".join(lines), kb


async def _send_shelter_overview(message: Message, tg_id: int, page: int = 0):
    async with async_session() as session:
        listings = await get_market_listings(session)
        text, kb = _build_shelter_view(listings, page)

    await message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())


@router.message(Command("shelter"))
@router.message(F.text == "🏯Приют")
async def shelter_entry(message: Message):
    tg_id = message.from_user.id
    await _send_shelter_overview(message, tg_id)


@router.callback_query(F.data.startswith("shelter:page:"))
async def shelter_page_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректные данные приюта.", show_alert=True)
        return

    _, _, page_str = parts
    try:
        page = int(page_str)
    except ValueError:
        await callback.answer("Некорректные данные приюта.", show_alert=True)
        return

    async with async_session() as session:
        listings = await get_market_listings(session)
        text, kb = _build_shelter_view(listings, page)

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "shelter:buy")
async def shelter_buy_callback(callback: CallbackQuery):
    tg_id = callback.from_user.id

    async with async_session() as session:
        listings = await get_market_listings(session)

        if not listings:
            await callback.answer("Сейчас нет Бетов на продажу.", show_alert=True)
            return

    await callback.message.answer(
        "Введите номер Бета, которого вы хотите купить👇🏼\n"
        "Например: 5",
    )
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("shelter:buy_confirm:"))
async def shelter_buy_confirm_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректные данные приюта.", show_alert=True)
        return

    _, _, listing_id_str = parts
    try:
        listing_id = int(listing_id_str)
    except ValueError:
        await callback.answer("Некорректные данные приюта.", show_alert=True)
        return

    tg_id = callback.from_user.id

    async with async_session() as session:
        result = await buy_listing(session, tg_id, listing_id)

    if not result.get("ok"):
        await callback.answer(result.get("message", "Покупка не удалась."), show_alert=True)
        return

    bet = result["bet"]
    bet_text = format_bet_short(bet)
    price = result["price"]
    buyer_neurons = result["buyer_neurons"]
    seller_tg_id = result.get("seller_tg_id")

    await callback.message.answer(
        "Покупка завершена!\n\n"
        f"Ты купил: <b>{bet_text}</b>\n"
        f"Стоимость: <b>{price}</b> нейронов\n"
        f"Всего нейронов теперь: <b>{buyer_neurons}</b>",
        parse_mode="HTML",
    )

    if seller_tg_id:
        try:
            await bot.send_message(
                chat_id=seller_tg_id,
                text=(
                    "Твоего Бета купили в приюте!\n\n"
                    f"Бет: <b>{bet_text}</b>\n"
                    f"Ты получил: <b>{price}</b> нейронов"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "shelter:cancel")
async def shelter_cancel_callback(callback: CallbackQuery):
    try:
        await callback.answer("Действие отменено.")
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "shelter:sell")
async def shelter_sell_callback(callback: CallbackQuery):
    tg_id = callback.from_user.id

    async with async_session() as session:
        player = await get_or_create_player(session, tg_id)
        bets_result = await session.scalars(
            select(Bet).where(
                Bet.owner_id == player.id,
                Bet.is_active == True,
                Bet.in_lab == False,
                Bet.in_shelter == False,
            )
        )
        bets = bets_result.all()

    if not bets:
        await callback.answer(
            "У тебя нет Бетов, которых можно выставить в приют.",
            show_alert=True,
        )
        return

    kb = InlineKeyboardBuilder()
    for bet in bets:
        kb.button(
            text=f"Продать {format_bet_short(bet)}",
            callback_data=f"shelter:sell_pick:{bet.id}",
        )
    kb.adjust(1)

    await callback.message.answer(
        "Выбери Бета, которого хочешь выставить в приют:",
        reply_markup=kb.as_markup(),
    )
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("shelter:sell_pick:"))
async def shelter_sell_pick_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректные данные приюта.", show_alert=True)
        return

    _, _, bet_id_str = parts
    try:
        bet_id = int(bet_id_str)
    except ValueError:
        await callback.answer("Некорректные данные приюта.", show_alert=True)
        return

    tg_id = callback.from_user.id

    async with async_session() as session:
        result = await start_sell_request(session, tg_id, bet_id)

    if not result.get("ok"):
        await callback.answer(result.get("message", "Не удалось начать продажу."), show_alert=True)
        return

    bet = result["bet"]
    min_price = result["min_price"]
    max_price = result["max_price"]
    bet_text = format_bet_short(bet)

    await callback.message.answer(
        "Продажа Бета в приют:\n\n"
        f"Бет: <b>{bet_text}</b>\n"
        f"Укажи цену в нейронах (числом).\n"
        f"Допустимый диапазон: от <b>{min_price}</b> до <b>{max_price}</b>.",
        parse_mode="HTML",
    )
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.message(F.text.regexp(r"^\d+$"))
async def shelter_price_input_handler(message: Message):
    tg_id = message.from_user.id

    number = int(message.text)

    # Сначала пытаемся интерпретировать число как цену продажи
    async with async_session() as session:
        sell_result = await finish_sell_request(session, tg_id, number)

    if sell_result.get("ok"):
        bet = sell_result["bet"]
        bet_text = format_bet_short(bet)
        price = sell_result["price"]

        await message.answer(
            "Бет выставлен в приют!\n\n"
            f"Бет: <b>{bet_text}</b>\n"
            f"Цена: <b>{price}</b> нейронов",
            parse_mode="HTML",
        )
        return

    # Если нет активного запроса на продажу — пробуем воспринять число как номер Бета для покупки
    if sell_result.get("reason") != "no_request":
        await message.answer(
            sell_result.get("message", "Не удалось выставить Бета в приют.")
        )
        return

    index = number

    async with async_session() as session:
        listings = await get_market_listings(session)

    if not listings:
        await message.answer("Сейчас нет Бетов на продажу.")
        return

    if index < 1 or index > len(listings):
        await message.answer("Бета с таким номером нет на рынке.")
        return

    item = listings[index - 1]
    rarity = str(item["bet_rarity"])
    emoji = RARITY_EMOJI.get(rarity, "⭐️")
    bet_text = f"{emoji}{item['bet_name']} ур.{item['bet_level']}"
    price = item["price"]
    listing_id = item["id"]

    kb = InlineKeyboardBuilder()
    kb.button(
        text="Подтвердить",
        callback_data=f"shelter:buy_confirm:{listing_id}",
    )
    kb.button(text="Отказаться", callback_data="shelter:cancel")
    kb.adjust(2)

    await message.answer(
        "Подтверждение покупки:\n\n"
        f"Ты хочешь купить <b>{bet_text}</b>\n"
        f"за <b>{price}</b> нейронов.\n\n"
        "Подтвердить сделку?",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )
