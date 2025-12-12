from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select

from bot.database.models.base import async_session
from bot.database.models.bets.bet import Bet
from bot.database.request.player_requests import get_or_create_player_for_user
from bot.service.lab_service import (
    LAB_DURATION_MINUTES,
    start_lab_for_bet,
    collect_lab_reward,
    calc_lab_total_reward,
)

router = Router()


RARITY_EMOJI = {
    "Обычный": "⭐️",
    "Редкий": "🌟",
    "Эпический": "💫",
    "Легендарный": "✨",
}


def format_bet_with_rarity(bet: Bet) -> str:
    rarity = str(bet.rarity)
    emoji = RARITY_EMOJI.get(rarity, "⭐️")
    return f"{emoji}{bet.name} (ур.{bet.level})"


@router.message(F.text == "🧪Лаборатория")
async def lab_overview_handler(message: Message):
    tg_id = message.from_user.id
    player = await get_or_create_player_for_user(tg_id)

    async with async_session() as session:
        lab_bets_result = await session.scalars(
            select(Bet).where(
                Bet.owner_id == player.id,
                Bet.is_active == True,
                Bet.in_lab == True,
            )
        )
        lab_bets = lab_bets_result.all()

        available_result = await session.scalars(
            select(Bet).where(
                Bet.owner_id == player.id,
                Bet.is_active == True,
                Bet.in_lab == False,
            )
        )
        available_bets = available_result.all()

    now = datetime.now(timezone.utc)

    lines = ["🧪 <b>Лаборатория</b>\n"]

    if lab_bets:
        total_expected = 0
        lines.append("Сейчас в лаборатории:")
        for bet in lab_bets:
            if bet.lab_ends_at:
                remaining = bet.lab_ends_at - now
                minutes_left = max(int(remaining.total_seconds() // 60), 0)
                if minutes_left > 0:
                    time_text = f"ещё ~{minutes_left} мин."
                else:
                    time_text = "готов к получению награды"
            else:
                time_text = "в работе"

            expected = calc_lab_total_reward(player, bet)
            total_expected += expected

            lines.append(
                f"• {format_bet_with_rarity(bet)} — {time_text}"
            )

        lines.append(
            f"\n⚗️ Ожидаемая суммарная награда: <b>{total_expected}</b> нейронов"
        )
    else:
        lines.append("Сейчас в лаборатории нет Бетов.")

    if available_bets:
        lines.append(
            "\nДоступные Беты, которых можно отправить в лабораторию:"
        )
    else:
        lines.append(
            "\nУ тебя нет свободных Бетов для лаборатории. "
            "Выведи Бета из лаборатории или получи нового через ношение."
        )

    kb = InlineKeyboardBuilder()

    # Кнопки для забора награды / просмотра Бетов в лаборатории
    for bet in lab_bets:
        bet_label = format_bet_with_rarity(bet)
        if bet.lab_ends_at and now >= bet.lab_ends_at:
            kb.button(
                text=f"Забрать награду: {bet_label}",
                callback_data=f"lab:collect:{bet.id}",
            )
        else:
            kb.button(
                text=f"Смотреть {bet.name}",
                callback_data=f"bet:{bet.id}",
            )

    # Кнопки для отправки новых Бетов в лабораторию
    for bet in available_bets:
        kb.button(
            text=f"Отправить: {format_bet_with_rarity(bet)}",
            callback_data=f"lab:start:{bet.id}",
        )

    if kb.buttons:
        kb.adjust(1)
        markup = kb.as_markup()
    else:
        markup = None

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=markup,
    )


@router.message(F.text == "🐾Мои беты")
async def my_bets_handler(message: Message):
    tg_id = message.from_user.id
    player = await get_or_create_player_for_user(tg_id)

    async with async_session() as session:
        result = await session.scalars(
            select(Bet)
            .where(
                Bet.owner_id == player.id,
                Bet.is_active == True,
                Bet.in_shelter == False,
            )
            .order_by(Bet.rarity, Bet.level.desc(), Bet.created_at)
        )
        bets = result.all()

    if not bets:
        await message.answer(
            "У тебя пока нет Бетов.\n"
            "Сделай первое ношение, чтобы получить своего первого питомца!"
        )
        return

    kb = InlineKeyboardBuilder()
    for bet in bets:
        btn_text = f"{bet.name} ({bet.rarity}) • ур. {bet.level}"
        kb.button(text=btn_text, callback_data=f"bet:{bet.id}")
    kb.adjust(1)

    await message.answer(
        "Твои Беты:\n"
        "Нажми на Бета, чтобы посмотреть его характеристики.",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("bet:"))
async def bet_details_callback(callback: CallbackQuery):
    tg_id = callback.from_user.id
    player = await get_or_create_player_for_user(tg_id)

    try:
        bet_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный выбор Бета.", show_alert=True)
        return

    async with async_session() as session:
        bet = await session.scalar(
            select(Bet).where(
                Bet.id == bet_id,
                Bet.owner_id == player.id,
                Bet.is_active == True,
                Bet.in_shelter == False,
            )
        )

    if not bet:
        await callback.answer(
            "Этот Бет не найден или больше недоступен.", show_alert=True
        )
        return

    now = datetime.now(timezone.utc)

    if bet.in_lab and bet.lab_ends_at:
        remaining = bet.lab_ends_at - now
        minutes_left = max(int(remaining.total_seconds() // 60), 0)
        lab_status = (
            f"🧪 В лаборатории ещё ~{minutes_left} мин."
            if minutes_left > 0
            else "🧪 Бет завершил работу в лаборатории и ждёт награду."
        )
    elif bet.in_lab:
        lab_status = "🧪 Бет сейчас в лаборатории."
    else:
        lab_status = "Бет не находится в лаборатории."

    created_at_str = (
        bet.created_at.strftime("%d.%m.%Y %H:%M") if bet.created_at else "неизвестно"
    )

    text = (
        f"🐾 <b>{bet.name}</b>\n"
        f"Редкость: <b>{bet.rarity}</b>\n"
        f"Уровень: <b>{bet.level}</b> / 60\n"
        f"Получен: <i>{created_at_str}</i>\n\n"
        f"{lab_status}"
    )

    kb = InlineKeyboardBuilder()

    if not bet.in_lab:
        kb.button(
            text="🧪 Отправить в лабораторию",
            callback_data=f"lab:start:{bet.id}",
        )
        kb.adjust(1)
        markup = kb.as_markup()
    else:
        if bet.lab_ends_at and now >= bet.lab_ends_at:
            kb.button(
                text="Забрать награду из лаборатории",
                callback_data=f"lab:collect:{bet.id}",
            )
            kb.adjust(1)
            markup = kb.as_markup()
        else:
            markup = None

    await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
    try:
        await callback.answer()
    except TelegramBadRequest:
        # Запрос мог «протухнуть», если бот перезапускался;
        # в этом случае просто игнорируем ошибку ответа на callback.
        pass


@router.callback_query(F.data.startswith("lab:start:"))
async def lab_start_choose_duration(callback: CallbackQuery):
    tg_id = callback.from_user.id

    try:
        bet_id = int(callback.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("Некорректный выбор Бета.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for minutes, label in LAB_DURATION_MINUTES.items():
        kb.button(
            text=label,
            callback_data=f"lab:duration:{bet_id}:{minutes}",
        )
    kb.adjust(2)

    await callback.message.answer(
        "Выбери длительность работы Бета в лаборатории:",
        reply_markup=kb.as_markup(),
    )

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("lab:duration:"))
async def lab_start_callback(callback: CallbackQuery):
    tg_id = callback.from_user.id

    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("Некорректные данные лаборатории.", show_alert=True)
        return

    _, _, bet_id_str, minutes_str = parts

    try:
        bet_id = int(bet_id_str)
        minutes = int(minutes_str)
    except ValueError:
        await callback.answer("Некорректные данные лаборатории.", show_alert=True)
        return

    async with async_session() as session:
        result = await start_lab_for_bet(session, tg_id, bet_id, minutes)

    if not result.get("ok"):
        await callback.answer(result.get("message", "Не удалось отправить в лабораторию."), show_alert=True)
        return

    await callback.message.answer(
        "🧪Бет отправлен в лабораторию!\n\n"
        f"Бет: <b>{result['bet_name']}</b>\n"
        f"Длительность: <b>{result['duration_label']}</b>\n"
        f"Ожидаемая награда: <b>{result['expected_reward']}</b> нейронов",
        parse_mode="HTML",
    )

    try:
        await callback.answer("Бет отправлен в лабораторию.")
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("lab:collect:"))
async def lab_collect_callback(callback: CallbackQuery):
    tg_id = callback.from_user.id

    try:
        bet_id = int(callback.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные лаборатории.", show_alert=True)
        return

    async with async_session() as session:
        result = await collect_lab_reward(session, tg_id, bet_id)

    if not result.get("ok"):
        await callback.answer(result.get("message", "Не удалось забрать награду."), show_alert=True)
        return

    xp_gained = result.get("xp_gained", 0)
    rank_before = result.get("rank_before")
    rank_after = result.get("rank_after")
    rank_ups = result.get("rank_ups", 0)

    await callback.message.answer(
        "Бет вернулся из лаборатории!\n\n"
        f"Бет: <b>{result['bet_name']}</b>\n"
        f"Ты получил: <b>{result['reward']}</b> нейронов\n"
        f"Опыт: +{xp_gained}\n\n"
        f"Всего нейронов теперь: <b>{result['player_neurons']}</b>",
        parse_mode="HTML",
    )

    if rank_ups and rank_before is not None and rank_after is not None:
        await callback.message.answer(
            f"ВАШ РАНГ ПОВЫШЕН: {rank_before} -> {rank_after}👏🏻"
        )

    try:
        await callback.answer("🌟Награда получена")
    except TelegramBadRequest:
        pass
