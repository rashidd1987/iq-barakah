"""Система Баракатов — реферальные баллы."""
import random
import string

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.models import User, BarakahTransaction, Payment

REFERRAL_PERCENT = 10  # % от суммы оплаты


def generate_referral_code(user_id: int) -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{user_id}{suffix}"


async def ensure_referral_code(session: AsyncSession, user: User) -> str:
    if not user.referral_code:
        user.referral_code = generate_referral_code(user.id)
        await session.flush()
    return user.referral_code


async def get_referrer(session: AsyncSession, user_id: int) -> User | None:
    user = await session.get(User, user_id)
    if not user or not user.referred_by:
        return None
    return await session.get(User, user.referred_by)


async def accrue_referral_barakah(
    session: AsyncSession,
    payment: Payment,
) -> int | None:
    """Начислить 10% от оплаты рефереру. Возвращает user_id реферера или None."""
    referrer = await get_referrer(session, payment.user_id)
    if not referrer:
        return None

    amount = round(payment.amount * REFERRAL_PERCENT / 100)
    if amount <= 0:
        return None

    referrer.barakah_balance += amount
    session.add(BarakahTransaction(
        user_id=referrer.id,
        amount=amount,
        kind="referral",
        ref_user_id=payment.user_id,
        payment_id=payment.id,
        note=f"10% от оплаты {payment.tariff_id} ({payment.amount}₽)",
    ))
    await session.flush()
    return referrer.id


async def spend_barakah(
    session: AsyncSession,
    user_id: int,
    amount: int,
    note: str = "",
) -> bool:
    """Списать баллы. Возвращает True если успешно."""
    user = await session.get(User, user_id)
    if not user or user.barakah_balance < amount:
        return False
    user.barakah_balance -= amount
    session.add(BarakahTransaction(
        user_id=user_id,
        amount=-amount,
        kind="spend",
        note=note,
    ))
    await session.flush()
    return True


async def get_transactions(session: AsyncSession, user_id: int, limit: int = 10) -> list[BarakahTransaction]:
    result = await session.execute(
        select(BarakahTransaction)
        .where(BarakahTransaction.user_id == user_id)
        .order_by(BarakahTransaction.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def get_referral_count(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count()).where(User.referred_by == user_id)
    )
    return result.scalar() or 0
