from aiogram import Router, F
from aiogram.types import Message

from bot.database.models.user import async_session
from bot.service.noshenie_service import do_noshenie
from bot.service.quote_service import fetch_random_quote

router = Router()


RARITY_EMOJI = {
    "Обычный": "⭐️",
    "Редкий": "🌟",
    "Эпический": "💫",
    "Легендарный": "✨",
}


@router.message(F.text == "🤲🏻Ношение")
async def noshenie_handler(message: Message):
    tg_id = message.from_user.id

    async with async_session() as session:
        result = await do_noshenie(session, tg_id)

    if not result["ok"] and result["reason"] == "cooldown":
        await message.answer(
            "Ты уже делал ношение недавно.\n"
            f"Попробуй снова через {result['remaining_minutes']} минут."
        )
        return

    if not result["ok"] and result["reason"] == "not_enough_neurons":
        await message.answer(
            "Недостаточно нейронов для ношения.\n"
            f"Нужно минимум {result['required_neurons']} нейронов, "
            f"у тебя сейчас {result['current_neurons']}."
        )
        return

    rarity = result["rarity"].value
    rarity_emoji = RARITY_EMOJI.get(rarity, "⭐️")
    bet_name = result["bet_name"]
    bet_level = result["bet_level"]
    neurons_spent = result["neurons_spent"]
    neurons_reward = result["neurons_reward"]
    total_neurons = result["total_neurons"]
    bets_count = result["bets_count"]
    xp_gained = result.get("xp_gained", 0)
    rank = result.get("rank")
    rank_before = result.get("rank_before", rank)
    rank_ups = result.get("rank_ups", 0)
    is_free = result.get("is_free", False)

    quote = await fetch_random_quote()
    if quote:
        quote_block = f'\n\n🗨 Цитата Бета:\n"<i>{quote}</i>"'
    else:
        quote_block = ""

    status_line = "Новый Бет! 🎉" if result["is_new_bet"] else "Уровень Бета повышен! 🔼"

    if is_free:
        cost_line = "Бесплатное ношение на сегодня ✅"
    else:
        cost_line = f"-{neurons_spent} нейронов за ношение"

    await message.answer(
        "✨ Ношение завершено!\n\n"
        f"{cost_line}\n"
        f"{status_line}\n"
        f"Бет: {rarity_emoji}<b>{bet_name}</b>\n"
        f"Редкость: <b>{rarity}</b>\n"
        f"Уровень Бета: <b>{bet_level}</b>\n\n"
        f"+{neurons_reward} нейронов награда\n"
        f"+{xp_gained} опыта\n\n"
        f"Всего нейронов: <b>{total_neurons}</b>\n"
        f"Всего Бетов: <b>{bets_count}</b>"
        f"{quote_block}",
        parse_mode="HTML",
    )

    if rank_ups and rank is not None and rank_before is not None:
        await message.answer(
            f"🐦‍🔥ВАШ РАНГ ПОВЫШЕН: {rank_before} -> {rank}🐦‍🔥"
        )
