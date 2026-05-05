import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()

WORKER_ID = os.getenv("WORKER_ID", "worker_1")

async def connect_db():
    """
    Keep trying to connect to DB
    until it's ready!
    Workers start before app sometimes
    so we need to wait patiently
    """
    import asyncpg
    for i in range(10):
        try:
            print(f"🔌 Trying DB connection... ({i+1}/10)")
            pool = await asyncpg.create_pool(
                dsn=os.getenv("DATABASE_URL"),
                min_size=2,
                max_size=5
            )
            print(f"✅ Connected to DB!")
            return pool
        except Exception as e:
            print(f"❌ DB not ready: {e}")
            await asyncio.sleep(3)
    raise Exception("Could not connect to DB after 10 tries!")

async def wait_for_tables(db_pool):
    """
    Wait until app has created the tables
    App creates tables on startup
    Workers must wait for this!
    """
    for i in range(20):
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1 FROM workers LIMIT 1")
            print(f"✅ Tables are ready!")
            return
        except Exception:
            print(f"⏳ Waiting for tables to be created... ({i+1}/20)")
            await asyncio.sleep(3)
    raise Exception("Tables never created!")

async def register_worker(db_pool):
    """
    Register this worker in database when it starts
    So scheduler knows it exists!
    """
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO workers (id, status, last_seen)
            VALUES ($1, 'online', NOW())
            ON CONFLICT (id)
            DO UPDATE SET status = 'online', last_seen = NOW()
        """, WORKER_ID)
    print(f"✅ Worker {WORKER_ID} registered in database!")

async def send_heartbeat(db_pool):
    """
    Send heartbeat every 5 seconds
    Tells scheduler I'm still alive!
    If heartbeat stops → worker marked DEAD
    """
    while True:
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE workers
                    SET last_seen = NOW(), status = 'online'
                    WHERE id = $1
                """, WORKER_ID)
        except Exception as e:
            print(f"❌ Heartbeat failed: {e}")
        await asyncio.sleep(5)

async def execute_job(job_id: int, db_pool):
    """
    Main job execution function
    1. Fetch job from DB
    2. Mark as RUNNING
    3. Execute based on type
    4. Mark as COMPLETED or FAILED
    """
    async with db_pool.acquire() as conn:

        # Step 1 - Get job details
        job = await conn.fetchrow("""
            SELECT * FROM jobs WHERE id = $1
        """, job_id)

        if not job:
            print(f"❌ Job {job_id} not found!")
            return

        print(f"🔄 Worker {WORKER_ID} executing job {job_id} ({job['type']})")

        # Step 2 - Mark as RUNNING
        await conn.execute("""
            UPDATE jobs
            SET status = 'running',
                worker_id = $1,
                started_at = NOW()
            WHERE id = $2
        """, WORKER_ID, job_id)

        # Step 3 - Execute based on type
        try:
            payload = json.loads(job["payload"]) if job["payload"] else {}
            result = None

            if job["type"] == "send_email":
                from app.jobs.email import execute_email_job
                result = await execute_email_job(payload)

            elif job["type"] == "resize_image":
                from app.jobs.image import execute_image_job
                result = await execute_image_job(payload)

            elif job["type"] == "generate_pdf":
                from app.jobs.pdf import execute_pdf_job
                result = await execute_pdf_job(payload)

            # Step 4 - Mark as COMPLETED
            await conn.execute("""
                UPDATE jobs
                SET status = 'completed',
                    result = $1,
                    finished_at = NOW()
                WHERE id = $2
            """, result, job_id)

            await conn.execute("""
                UPDATE workers
                SET jobs_completed = jobs_completed + 1
                WHERE id = $1
            """, WORKER_ID)

            print(f"✅ Job {job_id} completed! Result: {result}")

        except Exception as e:
            print(f"❌ Job {job_id} failed: {e}")
            retries = job["retries"] + 1

            if retries < job["max_retries"]:
                print(f"🔁 Retrying job {job_id} (attempt {retries}/{job['max_retries']})")
                await conn.execute("""
                    UPDATE jobs
                    SET status = 'pending',
                        retries = $1,
                        worker_id = NULL
                    WHERE id = $2
                """, retries, job_id)
                from app.queue.redis_queue import push_job
                await push_job(job_id, job["priority"])
            else:
                await conn.execute("""
                    UPDATE jobs
                    SET status = 'failed',
                        error = $1,
                        finished_at = NOW()
                    WHERE id = $2
                """, str(e), job_id)
                print(f"💀 Job {job_id} permanently failed!")

async def main():
    from app.queue.redis_queue import pop_job

    print(f"🚀 Worker {WORKER_ID} starting...")

    # Connect to DB with retries
    db_pool = await connect_db()

    # Wait for app to create tables
    await wait_for_tables(db_pool)

    # Register this worker
    await register_worker(db_pool)

    # Start heartbeat in background
    asyncio.create_task(send_heartbeat(db_pool))

    print(f"👀 Worker {WORKER_ID} waiting for jobs...")

    # Main polling loop
    while True:
        try:
            job_id = await pop_job()
            if job_id:
                await execute_job(job_id, db_pool)
        except Exception as e:
            print(f"❌ Worker error: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())