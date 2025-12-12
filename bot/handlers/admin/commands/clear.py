from datetime import datetime, timedelta, timezone

from aiogram import Router
from bot.handlers.client.commands.start import Command, bot, Message
from bot.keyboards.keyborad import main_keyboard
from bot.database.models.base import async_session
from bot.database.models.promo import PromoCode
from bot.service.noshenie_service import get_or_create_player
from sqlalchemy import select

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


DEFAULT_PROMO_REWARD_NEURONS = 500


@router.message(Command("promocreate"))
async def promo_create_command(message: Message):
    """
    Админская команда для создания промокодов.
    Формат:
    /promocreate CODE DAYS [MAX_USES]
    """
    parts = (message.text or "").split()

    if len(parts) < 3:
        await message.answer(
            "Формат команды:\n"
            "<code>/promocreate NEWYEAR 30 1000</code>\n\n"
            "где:\n"
            "<b>NEWYEAR</b> — код промо,\n"
            "<b>30</b> — срок действия в днях,\n"
            "<b>1000</b> — (необязательно) максимум игроков, которые могут его использовать.\n"
            "Если число игроков не указано, промокод будет без ограничения по использованию.",
            parse_mode="HTML",
        )
        return

    raw_code = parts[1]
    raw_days = parts[2]
    raw_max_uses = parts[3] if len(parts) >= 4 else None

    try:
        days = int(raw_days)
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Количество дней должно быть положительным числом.")
        return

    max_uses: int | None
    if raw_max_uses is None:
        max_uses = None
    else:
        try:
            max_uses = int(raw_max_uses)
            if max_uses <= 0:
                raise ValueError
        except ValueError:
            await message.answer(
                "Максимальное количество игроков должно быть положительным числом.",
            )
            return

    code = raw_code.strip().upper()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=days)

    async with async_session() as session:
        existing = await session.scalar(
            select(PromoCode).where(PromoCode.code == code)
        )

        if existing:
            existing.reward_neurons = DEFAULT_PROMO_REWARD_NEURONS
            existing.max_uses = max_uses
            existing.is_active = True
            existing.expires_at = expires_at
            # счётчик использований не трогаем
            promo = existing
        else:
            promo = PromoCode(
                code=code,
                reward_neurons=DEFAULT_PROMO_REWARD_NEURONS,
                max_uses=max_uses,
                used_count=0,
                is_active=True,
                expires_at=expires_at,
            )
            session.add(promo)

        await session.commit()

    limit_text = (
        f"до <b>{max_uses}</b> использований"
        if max_uses is not None
        else "без ограничения по количеству использований"
    )

    await message.answer(
        "Промокод создан.\n\n"
        f"Код: <b>{code}</b>\n"
        f"Награда: <b>{DEFAULT_PROMO_REWARD_NEURONS}</b> нейронов\n"
        f"Срок действия: <b>{days}</b> дней\n"
        f"Лимит: {limit_text}",
        parse_mode="HTML",
    )
