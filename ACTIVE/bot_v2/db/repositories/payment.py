from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_v2.db.models import Payment


class PaymentRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, tariff_id: str, amount: int,
                     yoo_payment_id: str | None = None, email: str | None = None) -> Payment:
        p = Payment(
            user_id=user_id, tariff_id=tariff_id, amount=amount,
            yoo_payment_id=yoo_payment_id, email_used=email, status="pending"
        )
        self.session.add(p)
        await self.session.flush()
        return p

    async def get_by_yoo_id(self, yoo_id: str) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.yoo_payment_id == yoo_id)
        )
        return result.scalar_one_or_none()

    async def get_pending(self, user_id: int) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.user_id == user_id, Payment.status == "pending")
            .order_by(Payment.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_paid(self, payment_id: int, tg_charge_id: str | None = None):
        p = await self.session.get(Payment, payment_id)
        if p:
            p.status = "paid"
            p.paid_at = datetime.now(timezone.utc)
            if tg_charge_id:
                p.tg_charge_id = tg_charge_id
            await self.session.flush()

    async def mark_failed(self, payment_id: int):
        p = await self.session.get(Payment, payment_id)
        if p:
            p.status = "failed"
            await self.session.flush()
