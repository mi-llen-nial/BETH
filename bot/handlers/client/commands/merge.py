from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, or_

from bot.core.loader import bot
from bot.database.models.base import async_session
from bot.database.models.bets.bet import Bet
from bot.database.models.bets.enums import RarityEnum
from bot.database.models.merge import MergeSession
from bot.database.models.players.player import Player
from bot.database.models.user import User
from bot.service.merge_service import (
    perform_merge,
    normalize_rarity,
    MERGE_COST_NEURONS,
)
from bot.service.noshenie_service import get_or_create_player

router = Router()


@router.message(Command("merge"))
@router.message(F.text == "🫂Слияние")
async def merge_command(message: Message):
    tg_id = message.from_user.id

    async with async_session() as session:
        player = await get_or_create_player(session, tg_id)

        # 1) Пытаемся найти самую раннюю сессию ожидания
        waiting_session = await session.scalar(
            select(MergeSession)
            .where(
                MergeSession.status == "waiting",
            )
            .order_by(MergeSession.created_at)
        )

        # 1а. Если есть сессия ожидания и она создана ДРУГИМ игроком — присоединяемся
        if waiting_session and waiting_session.player1_id != player.id:
            waiting_session.player2_id = player.id
            waiting_session.status = "confirm"
            await session.commit()
            session_id = waiting_session.id

            player1 = await session.get(Player, waiting_session.player1_id)
            player2 = await session.get(Player, waiting_session.player2_id)

            if not player1 or not player2:
                return

            player1_user = await session.scalar(
                select(User).where(User.id == player1.user_id)
            )
            player2_user = await session.scalar(
                select(User).where(User.id == player2.user_id)
            )

            if not player1_user or not player2_user:
                return

            player1_tg_id = player1_user.tg_id
            player2_tg_id = player2_user.tg_id

            text = (
                "Найден партнёр для слияния.\n\n"
                "Стоимость: {cost} нейронов с каждого.\n"
                "Один из вас повысит редкость выбранного Бэта,\n"
                "оба получат случайное количество нейронов\n"
                "(проигравший — x2).\n\n"
                "Подтвердить участие в слиянии?"
            ).format(cost=MERGE_COST_NEURONS)

            kb = InlineKeyboardBuilder()
            kb.button(text="Да", callback_data=f"merge_confirm:{session_id}:yes")
            kb.button(text="Нет", callback_data=f"merge_confirm:{session_id}:no")
            kb.adjust(2)

        else:
            # 1б. Подходящей чужой очереди нет — проверяем, не участвует ли игрок уже в своей сессии
            active_session = await session.scalar(
                select(MergeSession).where(
                    MergeSession.status.in_(["waiting", "confirm", "select_bet"]),
                    or_(
                        MergeSession.player1_id == player.id,
                        MergeSession.player2_id == player.id,
                    ),
                )
            )

            if active_session:
                kb = InlineKeyboardBuilder()
                kb.button(
                    text="Да",
                    callback_data=f"merge_cancel:{active_session.id}:yes",
                )
                kb.button(
                    text="Нет",
                    callback_data=f"merge_cancel:{active_session.id}:no",
                )
                kb.adjust(2)

                await message.answer(
                    "Вы уже участвуете в слиянии в состоянии очереди.\n"
                    "Отменить слияние?",
                    reply_markup=kb.as_markup(),
                )
                return

            # 2) Вообще никаких активных сессий нет — создаём новую очередь
            new_session = MergeSession(player1_id=player.id, status="waiting")
            session.add(new_session)
            await session.commit()

            await message.answer(
                "Ты в очереди на слияние.\n"
                "Как только найдётся партнёр, ты получишь уведомление."
            )
            return

    # Отправляем приглашения обоим игрокам (ветка, когда waiting_session найден и мы присоединились)
    await bot.send_message(
        chat_id=player1_tg_id,
        text=text,
        reply_markup=kb.as_markup(),
    )
    await bot.send_message(
        chat_id=player2_tg_id,
        text=text,
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("merge_cancel:"))
async def merge_cancel_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректные данные слияния.", show_alert=True)
        return

    _, session_id_str, decision = parts
    try:
        session_id = int(session_id_str)
    except ValueError:
        await callback.answer("Некорректные данные слияния.", show_alert=True)
        return

    if decision == "no":
        await callback.answer("Слияние остаётся активным.")
        await callback.message.edit_text(
            "Слияние не было отменено.", reply_markup=None
        )
        return

    user_tg_id = callback.from_user.id

    async with async_session() as session:
        merge_session = await session.get(MergeSession, session_id)
        if not merge_session or merge_session.status not in {
            "waiting",
            "confirm",
            "select_bet",
        }:
            await callback.answer("Слияние уже завершено или отменено.", show_alert=True)
            return

        player1 = await session.get(Player, merge_session.player1_id)
        player2 = (
            await session.get(Player, merge_session.player2_id)
            if merge_session.player2_id
            else None
        )

        # проверяем, что это участник сессии
        allowed_tg_ids = set()
        if player1:
            user1 = await session.scalar(select(User).where(User.id == player1.user_id))
            if user1:
                allowed_tg_ids.add(user1.tg_id)
        if player2:
            user2 = await session.scalar(select(User).where(User.id == player2.user_id))
            if user2:
                allowed_tg_ids.add(user2.tg_id)

        if user_tg_id not in allowed_tg_ids:
            await callback.answer("Ты не участник этого слияния.", show_alert=True)
            return

        merge_session.status = "cancelled"
        await session.commit()

    await callback.answer("Слияние отменено.")
    await callback.message.edit_text("Слияние отменено.", reply_markup=None)


@router.callback_query(F.data.startswith("merge_confirm:"))
async def merge_confirm_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректные данные слияния.", show_alert=True)
        return

    _, session_id_str, decision = parts

    try:
        session_id = int(session_id_str)
    except ValueError:
        await callback.answer("Некорректные данные слияния.", show_alert=True)
        return

    user_tg_id = callback.from_user.id

    async with async_session() as session:
        merge_session = await session.get(MergeSession, session_id)
        if not merge_session or merge_session.status != "confirm":
            await callback.answer("Это слияние уже недоступно.", show_alert=True)
            return

        if not merge_session.player2_id:
            await callback.answer("Слияние ещё не готово.", show_alert=True)
            return

        player1 = await session.get(Player, merge_session.player1_id)
        player2 = await session.get(Player, merge_session.player2_id)

        if not player1 or not player2:
            await callback.answer("Игроки не найдены.", show_alert=True)
            return

        player1_user = await session.scalar(
            select(User).where(User.id == player1.user_id)
        )
        player2_user = await session.scalar(
            select(User).where(User.id == player2.user_id)
        )

        if not player1_user or not player2_user:
            await callback.answer("Игроки не найдены.", show_alert=True)
            return

        if user_tg_id == player1_user.tg_id:
            is_player1 = True
        elif user_tg_id == player2_user.tg_id:
            is_player1 = False
        else:
            await callback.answer("Ты не участник этого слияния.", show_alert=True)
            return

        if decision == "no":
            merge_session.status = "cancelled"
            await session.commit()

            await callback.message.edit_text(
                "Ты отклонил слияние.", reply_markup=None
            )

            other_tg_id = player2_user.tg_id if is_player1 else player1_user.tg_id
            await bot.send_message(
                chat_id=other_tg_id,
                text="Слияние отменено другим игроком.",
            )

            await callback.answer()
            return

        if is_player1:
            merge_session.player1_confirmed = True
        else:
            merge_session.player2_confirmed = True

        await session.commit()
        await callback.answer("Ты подтвердил участие в слиянии.")

        await callback.message.edit_text(
            "Ты подтвердил участие в слиянии.\n"
            "Ожидаем подтверждение второго игрока.",
            reply_markup=None,
        )

        await session.refresh(merge_session)

        if merge_session.player1_confirmed and merge_session.player2_confirmed:
            merge_session.status = "select_bet"
            await session.commit()
            await session.refresh(merge_session)

            player1 = await session.get(Player, merge_session.player1_id)
            player2 = await session.get(Player, merge_session.player2_id)

            player1_user = await session.scalar(
                select(User).where(User.id == player1.user_id)
            )
            player2_user = await session.scalar(
                select(User).where(User.id == player2.user_id)
            )

            for player, slot in ((player1, 1), (player2, 2)):
                bets_result = await session.scalars(
                    select(Bet).where(
                        Bet.owner_id == player.id,
                        Bet.is_active == True,
                    )
                )
                bets = [
                    bet
                    for bet in bets_result
                    if normalize_rarity(bet.rarity) != RarityEnum.LEGENDARY
                ]

                if not bets:
                    await bot.send_message(
                        chat_id=(
                            player1_user.tg_id if slot == 1 else player2_user.tg_id
                        ),
                        text="У тебя нет подходящих Бэтов для слияния.",
                    )
                    continue

                kb = InlineKeyboardBuilder()
                for bet in bets:
                    kb.button(
                        text=f"{bet.name} ({bet.rarity}) • ур. {bet.level}",
                        callback_data=f"merge_pick:{merge_session.id}:{slot}:{bet.id}",
                    )
                kb.adjust(1)

                target_tg_id = (
                    player1_user.tg_id if slot == 1 else player2_user.tg_id
                )

                await bot.send_message(
                    chat_id=target_tg_id,
                    text="Выбери Бэта для слияния:",
                    reply_markup=kb.as_markup(),
                )


@router.callback_query(F.data.startswith("merge_pick:"))
async def merge_pick_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("Некорректные данные слияния.", show_alert=True)
        return

    _, session_id_str, slot_str, bet_id_str = parts

    try:
        session_id = int(session_id_str)
        slot = int(slot_str)
        bet_id = int(bet_id_str)
    except ValueError:
        await callback.answer("Некорректные данные слияния.", show_alert=True)
        return

    if slot not in (1, 2):
        await callback.answer("Некорректные данные слияния.", show_alert=True)
        return

    user_tg_id = callback.from_user.id

    async with async_session() as session:
        merge_session = await session.get(MergeSession, session_id)
        if not merge_session or merge_session.status != "select_bet":
            await callback.answer("Это слияние уже недоступно.", show_alert=True)
            return

        player1 = await session.get(Player, merge_session.player1_id)
        player2 = await session.get(Player, merge_session.player2_id)

        player = player1 if slot == 1 else player2

        if not player:
            await callback.answer("Игрок не найден.", show_alert=True)
            return

        user_row = await session.scalar(
            select(User).where(User.id == player.user_id)
        )
        if not user_row or user_row.tg_id != user_tg_id:
            await callback.answer("Это не твой выбор Бэта.", show_alert=True)
            return

        bet = await session.scalar(
            select(Bet).where(
                Bet.id == bet_id,
                Bet.owner_id == player.id,
                Bet.is_active == True,
            )
        )

        if not bet:
            await callback.answer("Этот Бэт не найден.", show_alert=True)
            return

        if normalize_rarity(bet.rarity) == RarityEnum.LEGENDARY:
            await callback.answer(
                "Легендарных Бэтов нельзя отправлять на слияние.",
                show_alert=True,
            )
            return

        if slot == 1:
            merge_session.player1_bet_id = bet.id
        else:
            merge_session.player2_bet_id = bet.id

        await session.commit()

        await callback.answer("Бэт выбран для слияния.")
        await callback.message.edit_text(
            "Ты выбрал Бэта для слияния.\n"
            "Ожидаем выбор второго игрока.",
            reply_markup=None,
        )

        await session.refresh(merge_session)

        if merge_session.player1_bet_id and merge_session.player2_bet_id:
            # снова получим tg_id игроков
            player1_user = await session.scalar(
                select(User)
                .join_from(
                    User,
                    Player,
                    Player.user_id == User.id,
                )
                .where(Player.id == merge_session.player1_id)
            )
            player2_user = await session.scalar(
                select(User)
                .join_from(
                    User,
                    Player,
                    Player.user_id == User.id,
                )
                .where(Player.id == merge_session.player2_id)
            )

            result = await perform_merge(
                session=session,
                initiator_tg_id=player1_user.tg_id,
                partner_tg_id=player2_user.tg_id,
                initiator_bet_id=merge_session.player1_bet_id,
                partner_bet_id=merge_session.player2_bet_id,
            )

            if not result.get("ok"):
                await bot.send_message(
                    chat_id=player1_user.tg_id,
                    text=f"Слияние не удалось:\n{result.get('message', 'Неизвестная ошибка.')}",
                )
                await bot.send_message(
                    chat_id=player2_user.tg_id,
                    text=f"Слияние не удалось:\n{result.get('message', 'Неизвестная ошибка.')}",
                )
                return

            # Подготовим отдельные тексты для победителя и проигравшего
            winner_tg_id = result["winner_tg_id"]
            loser_tg_id = result["loser_tg_id"]

            if winner_tg_id == player1_user.tg_id:
                winner_user = player1_user
                loser_user = player2_user
            else:
                winner_user = player2_user
                loser_user = player1_user

            winner_name = winner_user.first_name or winner_user.username or "игроком"

            winner_text = (
                "Слияние завершено успешно!🌟\n\n"
                f"Победа за {winner_name}\n"
                f"Бет <b>{result['winner_bet_name']}</b> повысил редкость до "
                f"<b>{result['winner_new_rarity'].value}</b>!\n"
                f"Вы получили {result['winner_neurons_gain']} нейронов"
            )

            loser_text = (
                "Слияние завершено успешно!🌟\n\n"
                f"Победа за {winner_name}\n"
                f"Ваш бет <b>{result['loser_bet_name']}</b> проигран!\n"
                f"Вы получили {result['loser_neurons_gain']} нейронов"
            )

            await bot.send_message(
                chat_id=winner_tg_id,
                text=winner_text,
                parse_mode="HTML",
            )
            await bot.send_message(
                chat_id=loser_tg_id,
                text=loser_text,
                parse_mode="HTML",
            )

            merge_session.status = "completed"
            await session.commit()
