from aiogram import Router, F
from aiogram.types import Message

from bot.database.models.user import async_session
from bot.service.noshenie_service import do_noshenie
from bot.service.quote_service import fetch_random_quote

router = Router()


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
    bet_name = result["bet_name"]
    bet_level = result["bet_level"]
    neurons_spent = result["neurons_spent"]
    neurons_reward = result["neurons_reward"]
    total_neurons = result["total_neurons"]
    bets_count = result["bets_count"]

    quote = await fetch_random_quote()
    if quote:
        quote_block = f'\n\n🗨 Цитата Бэта:\n"<i>{quote}</i>"'
    else:
        quote_block = ""

    status_line = "Новый Бэт! 🎉" if result["is_new_bet"] else "Уровень Бэта повышен! 🔼"

    await message.answer(
        "✨ Ношение завершено!\n\n"
        f"{status_line}\n"
        f"Бэт: <b>{bet_name}</b>\n"
        f"Редкость: <b>{rarity}</b>\n"
        f"Уровень Бэта: <b>{bet_level}</b>\n\n"
        f"-{neurons_spent} нейронов за ношение\n"
        f"+{neurons_reward} нейронов награда\n\n"
        f"Всего нейронов: <b>{total_neurons}</b>\n"
        f"Всего Бэтов: <b>{bets_count}</b>"
        f"{quote_block}",
        parse_mode="HTML",
    )
