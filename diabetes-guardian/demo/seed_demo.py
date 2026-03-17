"""
demo/seed_demo.py

One-time seed script for demo data. Writes directly to PostgreSQL (bypasses Gateway).
Generates 7 days of historical CGM, HR, exercise, user profile, weekly patterns,
known places, and emergency contacts.

Usage: python demo/seed_demo.py --user_id user_001
"""

import argparse
import asyncio
import random
import sys
from datetime import datetime, time, timedelta

sys.path.insert(0, ".")

from db.models import (
    User,
    UserCGMLog,
    UserEmergencyContact,
    UserExerciseLog,
    UserHRLog,
    UserKnownPlace,
    UserWeeklyPattern,
)
from db.session import AsyncSessionLocal


async def seed(user_id: str) -> None:
    """Generate all demo seed data for a single user."""
    async with AsyncSessionLocal() as session:
        print(f"Seeding data for {user_id}...")

        # ── User Profile ────────────────────────────────────
        user = User(
            user_id=user_id,
            name="Demo User",
            birth_year=1990,
            gender="male",
            waist_cm=85.0,
            weight_kg=78.0,
            height_cm=175.0,
        )
        await session.merge(user)
        await session.commit()
        print("  ✓ User profile")

        # ── Weekly Patterns ─────────────────────────────────
        # Resistance training on Mon(0), Wed(2), Sat(5) at 14:00–15:30
        for dow in [0, 2, 5]:
            pattern = UserWeeklyPattern(
                user_id=user_id,
                day_of_week=dow,
                start_time=time(14, 0),
                end_time=time(15, 30),
                activity_type="resistance_training",
            )
            session.add(pattern)
        await session.commit()
        print("  ✓ Weekly patterns (Mon/Wed/Sat 14:00–15:30)")

        # ── Known Places ────────────────────────────────────
        places = [
            ("Home", "home", 1.3521, 103.8198),
            ("Gym", "gym", 1.3200, 103.8400),
            ("Office", "office", 1.2800, 103.8500),
        ]
        for name, ptype, lat, lng in places:
            session.add(UserKnownPlace(
                user_id=user_id,
                place_name=name,
                place_type=ptype,
                gps_lat=lat,
                gps_lng=lng,
            ))
        await session.commit()
        print("  ✓ Known places (Home, Gym, Office)")

        # ── Emergency Contacts ──────────────────────────────
        session.add(UserEmergencyContact(
            user_id=user_id,
            contact_name="Mom",
            phone_number="+6591234567",
            relationship="family",
            notify_on=["hard_low_glucose", "hard_high_hr", "data_gap"],
        ))
        await session.commit()
        print("  ✓ Emergency contact (Mom)")

        # ── Historical CGM (past 7 days, NOT today) ─────────
        today_start = datetime.combine(datetime.now().date(), time(0, 0))
        cgm_records = []
        for day_offset in range(7, 0, -1):  # 7 days ago to yesterday
            day_base = today_start - timedelta(days=day_offset)
            for minute_offset in range(0, 1440, 10):  # Every 10 min
                ts = day_base + timedelta(minutes=minute_offset)
                # Simulate normal glucose curve: 5.0–8.0 with meal spikes
                hour = ts.hour
                if 7 <= hour <= 8:
                    base = 6.5 + random.gauss(0, 0.3)  # Post-breakfast
                elif 12 <= hour <= 13:
                    base = 7.0 + random.gauss(0, 0.4)  # Post-lunch
                elif 18 <= hour <= 19:
                    base = 7.5 + random.gauss(0, 0.4)  # Post-dinner
                else:
                    base = 5.5 + random.gauss(0, 0.3)  # Fasting baseline

                glucose = max(3.5, min(12.0, base))
                cgm_records.append(UserCGMLog(
                    user_id=user_id,
                    recorded_at=ts,
                    glucose=round(glucose, 2),
                ))

        session.add_all(cgm_records)
        await session.commit()
        print(f"  ✓ CGM records: {len(cgm_records)} entries (7 days)")

        # ── Historical HR (past 7 days, NOT today) ──────────
        hr_records = []
        for day_offset in range(7, 0, -1):
            day_base = today_start - timedelta(days=day_offset)
            for minute_offset in range(0, 1440, 10):
                ts = day_base + timedelta(minutes=minute_offset)
                hr = random.randint(60, 80)
                hr_records.append(UserHRLog(
                    user_id=user_id,
                    recorded_at=ts,
                    heart_rate=hr,
                    gps_lat=1.3521 + random.gauss(0, 0.001),
                    gps_lng=103.8198 + random.gauss(0, 0.001),
                ))

        session.add_all(hr_records)
        await session.commit()
        print(f"  ✓ HR records: {len(hr_records)} entries (7 days)")

        # ── Exercise History (3 sessions in past 7 days) ────
        exercise_days = [3, 5, 7]  # 3, 5, 7 days ago
        for day_offset in exercise_days:
            start = today_start - timedelta(days=day_offset) + timedelta(hours=14)
            end = start + timedelta(hours=1, minutes=30)
            session.add(UserExerciseLog(
                user_id=user_id,
                exercise_type="resistance_training",
                started_at=start,
                ended_at=end,
                avg_heart_rate=random.randint(130, 155),
                calories_burned=round(random.uniform(350, 450), 1),
            ))
        await session.commit()
        print("  ✓ Exercise history: 3 resistance training sessions")

        print(f"\n✅ Seed complete for {user_id}")
        print("   Note: No data written for today — data_gap scenario is testable.")
        print("\n   Next step: python pipeline/run.py --backfill --user_id " + user_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data")
    parser.add_argument("--user_id", type=str, default="user_001", help="User ID to seed")
    args = parser.parse_args()
    asyncio.run(seed(args.user_id))


if __name__ == "__main__":
    main()
