import asyncio

from aiohttp import web
from aiogram import types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot.core.loader import bot, dispathcer, Bot
from bot.core.config import WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT
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
from bot.database.models.user import async_main
from bot.database.models.base import Base, engine
from bot.database.models.players import player
from bot.database.models.bets import bet


async def tip_command(bot: Bot):
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


async def run_polling() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await async_main()
    setup_routers()
    await tip_command(bot)

    print("Start success (polling)")
    await dispathcer.start_polling(bot)


async def create_webhook_app() -> web.Application:
    """
    Создаём aiohttp‑приложение для работы через вебхуки.
    Эта функция используется как entrypoint для web.run_app().
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await async_main()
    setup_routers()
    await tip_command(bot)

    app = web.Application()
    SimpleRequestHandler(dispathcer, bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dispathcer, bot=bot)

    if not WEBHOOK_URL:
        raise RuntimeError(
            "WEBHOOK_URL не задан, но выбран режим вебхуков. "
            "Установи переменную окружения WEBHOOK_URL."
        )

    await bot.set_webhook(WEBHOOK_URL)
    print(f"Start success (webhook) on {WEBAPP_HOST}:{WEBAPP_PORT}, path={WEBHOOK_PATH}")
    return app


if __name__ == "__main__":
    try:
        if WEBHOOK_URL:
            # Режим вебхуков (для продакшн‑деплоя, например на Sourcecraft)
            web.run_app(create_webhook_app(), host=WEBAPP_HOST, port=WEBAPP_PORT)
        else:
            # Локальная разработка — long polling
            asyncio.run(run_polling())
    except KeyboardInterrupt:
        print("Exit success")
