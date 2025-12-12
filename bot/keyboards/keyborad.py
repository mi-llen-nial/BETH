from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='👤Профиль')],
        [KeyboardButton(text='🤲🏻Ношение'), KeyboardButton(text='🐾Мои беты')],
        [KeyboardButton(text='🧬Слияние'), KeyboardButton(text='🧪Лаборатория')],
        [KeyboardButton(text='🏯Приют')],
    ],
    resize_keyboard=True,
    input_field_placeholder='Выбери пункт...',
)

command = ['Настройки', 'Cтатистка', 'Мой аккаунт', 'Конфигурация']


async def reply_btns():
    keyboard = ReplyKeyboardBuilder()
    for btn in command:
        keyboard.add(KeyboardButton(text=btn))
    return keyboard.adjust(2).as_markup(resize_keyboard=True)

# async def inline_btns():
#     keyboard = InlineKeyboardBuilder()
#     for btn in command:
#         keyboard.add(InlineKeyboardButton(text=btn, url='https://translate.google.com/?hl=ru&sl=ru&tl=en&text=%D0%B2%D0%B2%D0%BE%D0%B4&op=translate'))
#     return keyboard.adjust(1).as_markup()
