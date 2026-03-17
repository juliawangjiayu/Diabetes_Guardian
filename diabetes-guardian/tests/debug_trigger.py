import asyncio
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.session import AsyncSessionLocal
from db.models import InterventionLog, User
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        # Check User
        res = await session.execute(select(User).where(User.user_id == "user_001"))
        u = res.scalar_one_or_none()
        if u:
            print(f"User: birth_year={u.birth_year}")
        else:
            print("User not found")
            
        # Check log
        res = await session.execute(
            select(InterventionLog)
            .where(InterventionLog.user_id == "user_001")
            .order_by(InterventionLog.triggered_at.desc())
            .limit(5)
        )
        logs = res.scalars().all()
        print(f"\nLast {len(logs)} Intervention Logs:")
        for l in logs:
            print(f"ID={l.id} Time={l.triggered_at} Trigger={l.trigger_type} Decision={l.agent_decision}")

if __name__ == "__main__":
    asyncio.run(main())
