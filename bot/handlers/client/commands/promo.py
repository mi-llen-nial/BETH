from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.database.models.base import async_session
from bot.service.promo_service import redeem_promo

router = Router()


@router.message(Command("promo"))
async def promo_command(message: Message):
    text = message.text or ""
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "Чтобы использовать промокод, отправь его вместе с командой.\n\n"
            "Например:\n"
            "<code>/promo BETHSTART</code>",
            parse_mode="HTML",
        )
        return

    code = parts[1].strip()

    async with async_session() as session:
        result = await redeem_promo(session, message.from_user.id, code)

    if not result.get("ok"):
        reason = result.get("reason")
        if reason == "not_found":
            text = "Такого промокода нет или он уже недоступен."
        elif reason == "expired":
            text = "Срок действия этого промокода истёк."
        elif reason == "limit":
            text = "Лимит использований этого промокода уже исчерпан."
        elif reason == "already_used":
            text = "Ты уже использовал этот промокод."
        elif reason == "empty":
            text = (
                "Нужно указать код после команды.\n"
                "Пример: <code>/promo BETHSTART</code>"
            )
        else:
            text = "Не удалось активировать промокод."

        await message.answer(text, parse_mode="HTML")
        return

    await message.answer(
        "Промокод активирован! 🎁\n\n"
        f"Код: <b>{result['code']}</b>\n"
        f"Ты получил: <b>{result['reward']}</b> нейронов\n"
        f"Всего нейронов теперь: <b>{result['total_neurons']}</b>",
        parse_mode="HTML",
    )

