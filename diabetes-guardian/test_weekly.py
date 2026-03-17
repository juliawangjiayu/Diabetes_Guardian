import asyncio
from sqlalchemy import select
from db.session import AsyncSessionLocal
from db.models import UserWeeklyPattern

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserWeeklyPattern).where(UserWeeklyPattern.user_id == 'user_001')
        )
        patterns = result.scalars().all()
        print(f'Total patterns: {len(patterns)}')
        for p in patterns:
            print(f'  ID={p.id} day={p.day_of_week} start={p.start_time} end={p.end_time} type={p.activity_type}')

asyncio.run(check())
