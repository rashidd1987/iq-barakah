import unittest

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot_v2.db.models import Participant, TaskCompletion, User, WeekAck
from bot_v2.db.repositories.participant import ParticipantRepo


class ParticipantReactivationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda c: User.metadata.create_all(
                c, tables=[User.__table__, Participant.__table__, WeekAck.__table__, TaskCompletion.__table__]
            ))
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)()
        self.session.add(User(id=123, name="Test participant"))
        await self.session.flush()
        self.repo = ParticipantRepo(self.session)

    async def asyncTearDown(self):
        await self.session.close()
        await self.engine.dispose()

    async def test_reactivate_graduate_preserves_identity_and_history(self):
        participant = await self.repo.activate(123, "А", 6, "III")
        original_id = participant.id
        self.session.add(WeekAck(user_id=123, level="А", week=6))
        self.session.add(TaskCompletion(user_id=123, level="А", week=6, task_index=0))
        await self.repo.graduate(123)
        await self.session.commit()
        self.assertIsNone(await self.repo.get(123))

        restored = await self.repo.activate(123, "Б", 1)
        await self.session.commit()
        self.assertEqual(restored.id, original_id)
        self.assertTrue(restored.is_active)
        self.assertIsNone(restored.graduated_at)
        self.assertEqual((restored.level, restored.week, restored.vakt_level), ("Б", 1, "III"))
        for model in [Participant, WeekAck, TaskCompletion]:
            count = await self.session.scalar(select(func.count()).select_from(model))
            self.assertEqual(count, 1)

    async def test_reactivate_same_step_keeps_skill_and_other_user_inactive(self):
        participant = await self.repo.activate(123, "А", 6, "III")
        self.session.add(User(id=456, name="Other participant"))
        await self.session.flush()
        other = await self.repo.activate(456, "Б", 4, "II")
        await self.repo.deactivate(456)
        await self.repo.deactivate(123)
        restored = await self.repo.activate(123, "А", 6)
        self.assertEqual(restored.id, participant.id)
        self.assertEqual((restored.week, restored.vakt_level), (6, "III"))
        self.assertFalse(other.is_active)
        self.assertEqual((other.level, other.week), ("Б", 4))

    async def test_explicit_skill_update_and_repeated_activation(self):
        first = await self.repo.activate(123, "А", 2, "I")
        second = await self.repo.activate(123, "А", 2, "III")
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.vakt_level, "III")
        self.assertEqual(await self.session.scalar(select(func.count()).select_from(Participant)), 1)


if __name__ == "__main__":
    unittest.main()
