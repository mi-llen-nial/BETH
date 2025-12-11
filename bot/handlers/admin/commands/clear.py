from aiogram import Router
from bot.handlers.client.commands.start import Command, bot, Message
from bot.keyboards.keyborad import main_keyboard
from bot.database.models.base import async_session
from bot.service.noshenie_service import get_or_create_player

router = Router()


@router.message(Command('clear'))
async def __(message: Message):
    chat_id = message.chat.id
    info = await message.answer(
        '🧹Очистка чата... \n\n<i>Подождите, может занять несколько минут</i>',
        parse_mode='HTML',
    )
    try:
        for i in range(message.message_id, message.message_id - 100, -1):
            try:
                await bot.delete_message(chat_id, i)
            except:  
                pass
    except Exception as e:
        await bot.send_message(chat_id, f'Ошибка при удалении: {e}')

    await bot.edit_message_text(
        chat_id=info.chat.id,
        message_id=info.message_id,
        text='Чат очищен🫧',
    )
    await message.answer('Выберите действие:', reply_markup=main_keyboard)


@router.message(Command('09124467_neurons'))
async def give_neurons_bonus(message: Message):
    tg_id = message.from_user.id

    async with async_session() as session:
        player = await get_or_create_player(session, tg_id)
        player.neurons += 1000
        await session.commit()

    await message.answer('Тебе начислено <b>1000 нейронов</b> 🎁', parse_mode='HTML')
