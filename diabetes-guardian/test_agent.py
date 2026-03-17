import asyncio
import json
import logging
import sys
from datetime import datetime
from agent.main import _run_graph

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

async def test():
    print("STARTING TEST SCRIPT")
    task = {
        "user_id": "user_001",
        "trigger_type": "SOFT_RAPID_SLOPE",
        "trigger_at": datetime.now().isoformat(),
        "current_glucose": 5.0,
        "gps_lat": None,
        "gps_lng": None,
        "context_notes": "Glucose falling rapidly"
    }
    try:
        print("CALLING _run_graph")
        await _run_graph(json.dumps(task))
        print("FINISHED _run_graph SUCCESSFULLY")
    except Exception as e:
        print(f"EXCEPTION CAUGHT: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
