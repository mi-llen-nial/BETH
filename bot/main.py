import asyncio
import json
from typing import Any, Dict

from aiogram import types

from bot.core.loader import bot, dispathcer, Bot
from bot.handlers.client.commands import (
    start,
    my_bet,
    general,
    profile,
    noshenie,
    merge,
    promo,
    shelter,
)
from bot.handlers.admin.commands import clear
from bot.database.models.base import Base, engine
from bot.database.models.user import async_main


BOT_INITIALIZED = False


async def tip_command(bot: Bot) -> None:
    commands = [
        types.BotCommand(command="start", description="Играть с BETH"),
        types.BotCommand(command="about", description="Описание про BETH"),
        types.BotCommand(command="news", description="Новости"),
        types.BotCommand(command="help", description="Получить помощь"),
        types.BotCommand(command="promo", description="Использовать промокод"),
    ]
    await bot.set_my_commands(commands)


def setup_routers() -> None:
    dispathcer.include_router(start.router)
    dispathcer.include_router(clear.router)
    dispathcer.include_router(my_bet.router)
    dispathcer.include_router(shelter.router)
    dispathcer.include_router(promo.router)
    dispathcer.include_router(merge.router)
    dispathcer.include_router(general.router)
    dispathcer.include_router(profile.router)
    dispathcer.include_router(noshenie.router)


async def _ensure_initialized() -> None:
    """
    Ленивая инициализация БД, роутеров и команд.
    Вызывается перед обработкой каждого апдейта, но выполняется один раз.
    """
    global BOT_INITIALIZED
    if BOT_INITIALIZED:
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await async_main()
    setup_routers()
    await tip_command(bot)

    BOT_INITIALIZED = True


async def _process_update(update_data: Dict[str, Any]) -> None:
    await _ensure_initialized()

    update = types.Update.model_validate(update_data)
    await dispathcer.feed_update(bot, update)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Синхронный entry‑point для Yandex Cloud Function.

    Ожидаемый формат `event` при HTTP‑триггере:
    {
        "body": "<raw JSON update from Telegram>",
        ...
    }
    """
    # Достаём тело запроса
    body = event.get("body", event)

    try:
        if isinstance(body, (bytes, bytearray)):
            body = body.decode("utf-8")

        if isinstance(body, str):
            body = body.strip()
            if not body:
                return {"statusCode": 200, "body": ""}
            update_data = json.loads(body)
        elif isinstance(body, dict) and "update_id" in body:
            # В некоторых случаях апдейт может прилететь сразу как dict
            update_data = body
        else:
            # Непонятный формат — просто отвечаем 200, чтобы Telegram не ретраил
            return {"statusCode": 200, "body": ""}
    except Exception:
        # Не смогли распарсить апдейт — игнорируем
        return {"statusCode": 200, "body": ""}

    # Запускаем асинхронную обработку апдейта
    asyncio.run(_process_update(update_data))

    # Фиктивный HTTP‑ответ, которого достаточно для Telegram / Яндекса
    return {"statusCode": 200, "body": ""}
