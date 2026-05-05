import redis.asyncio as redis
import os
from dotenv import load_dotenv

load_dotenv()

_redis = None

async def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            os.getenv("REDIS_URL"),
            decode_responses=True
        )
    return _redis

async def push_job(job_id: int, priority: str):
    r = await get_redis()
    queue_name = f"jobs:{priority}"

    await r.lpush(queue_name, job_id)
    print(f"📥 Job {job_id} pushed to {queue_name}")

async def pop_job():
    r = await get_redis()

    while True:
        result = await r.brpop(
            ["jobs:high", "jobs:medium", "jobs:low"],
            timeout=0
        )

        if result:
            queue_name, job_id = result
            print(f"📤 Job {job_id} popped from {queue_name}")
            return int(job_id)

async def get_queue_lengths():
    r = await get_redis()

    return {
        "high": await r.llen("jobs:high"),
        "medium": await r.llen("jobs:medium"),
        "low": await r.llen("jobs:low")
    }