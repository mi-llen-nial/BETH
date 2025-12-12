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
    text = (
        f"Добро пожаловать, {message.from_user.first_name}!\n\n"
        "Я BETH — игровой бот с Бетами.\n\n"
        "Что делать дальше:\n"
        "• Открой <b>👤Профиль</b>, чтобы посмотреть ранг и нейроны.\n"
        "• Нажми <b>🤲🏻Ношение</b>, чтобы получить Бета (есть одно бесплатное ношение в день).\n"
        "• В <b>🐾Мои беты</b> сможешь смотреть Бетов и отправлять их в лабораторию.\n"
        "• В <b>🧬Слияние</b> усиливай Бетов вместе с другими игроками.\n"
        "• В <b>🧪Лаборатории</b> Беты добывают нейроны, пока ты отдыхаешь.\n"
        "• В <b>🏯Приюте</b> можно покупать и продавать Бетов.\n\n"
        "Подробнее о механиках — в команде <b>/about</b>."
    )
    await message.answer(text, reply_markup=main_keyboard, parse_mode="HTML")
