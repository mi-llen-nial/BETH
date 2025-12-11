import aiogram
from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command
from bot.keyboards.keyborad import main_keyboard
from bot.core.loader import bot
from bot.database.requests import set_user

router = Router()

@router.message(Command('start'))
async def __(message: Message):
    await set_user(message.from_user)
    await message.answer(f'Добро пожаловать, {message.from_user.first_name}', 
                        reply_markup=main_keyboard)

