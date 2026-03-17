import asyncio
from sqlalchemy import select
from db.session import AsyncSessionLocal
from db.models import InterventionLog

async def check():
    async with AsyncSessionLocal() as session:
        stmt = select(InterventionLog).filter(InterventionLog.user_id == 'user_001').order_by(InterventionLog.id.desc()).limit(5)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        
        print(f"Total rows retrieved: {len(rows)}")
        for r in rows:
            print(f"ID: {r.id} | Trigger: {r.trigger_type} | Message: {r.message_sent[:50] if r.message_sent else 'None'} | Created: {r.created_at}")

if __name__ == "__main__":
    asyncio.run(check())
