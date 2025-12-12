import asyncio
from aiogram import types
from bot.core.loader import bot, dispathcer, Bot
from bot.handlers.client.commands import start, my_bet, general, profile, noshenie, merge
from bot.handlers.admin.commands import clear
from bot.database.models.user import async_main
from bot.database.models.base import Base, engine
from bot.database.models.players import player
from bot.database.models.bets import bet

async def tip_command(bot: Bot):
    commands = [
        types.BotCommand(command='start', description='Играть с BETH'), 
        types.BotCommand(command='about', description='Описание про BETH'),
        types.BotCommand(command='news', description='Новости'),
        types.BotCommand(command='help', description='Получить помощь'),
    ]
    await bot.set_my_commands(commands)

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await async_main()

    dispathcer.include_router(start.router)
    dispathcer.include_router(clear.router)
    dispathcer.include_router(my_bet.router)
    dispathcer.include_router(merge.router)
    dispathcer.include_router(general.router)
    dispathcer.include_router(profile.router)
    dispathcer.include_router(noshenie.router)

    print('Start success')
    await dispathcer.start_polling(bot)
    await tip_command(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit success')

