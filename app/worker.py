import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()

WORKER_ID = os.getenv("WORKER_ID", "worker_1")

async def connect_db():
    import asyncpg
    for i in range(10):
        try:
            print("🔌 Trying DB connection... (" + str(i+1) + "/10)")
            pool = await asyncpg.create_pool(
                dsn=os.getenv("DATABASE_URL"),
                min_size=2,
                max_size=5
            )
            print("✅ Connected to DB!")
            return pool
        except Exception as e:
            print("❌ DB not ready: " + str(e))
            await asyncio.sleep(3)
    raise Exception("Could not connect to DB after 10 tries!")

async def wait_for_tables(db_pool):
    for i in range(20):
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1 FROM workers LIMIT 1")
            print("✅ Tables are ready!")
            return
        except Exception:
            print("⏳ Waiting for tables... (" + str(i+1) + "/20)")
            await asyncio.sleep(3)
    raise Exception("Tables never created!")

async def register_worker(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO workers (id, status, last_seen)
            VALUES ($1, 'online', NOW())
            ON CONFLICT (id)
            DO UPDATE SET status = 'online', last_seen = NOW()
        """, WORKER_ID)
    print("✅ Worker " + WORKER_ID + " registered!")

async def send_heartbeat(db_pool):
    while True:
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE workers
                    SET last_seen = NOW(), status = 'online'
                    WHERE id = $1
                """, WORKER_ID)
        except Exception as e:
            print("❌ Heartbeat failed: " + str(e))
        await asyncio.sleep(5)

async def execute_job(job_id: int, db_pool):
    async with db_pool.acquire() as conn:
        job = await conn.fetchrow("""
            SELECT * FROM jobs WHERE id = $1
        """, job_id)

        if not job:
            print("❌ Job " + str(job_id) + " not found!")
            return

        print("🔄 Worker " + WORKER_ID + " executing job " + str(job_id) + " (" + job["type"] + ")")

        await conn.execute("""
            UPDATE jobs
            SET status = 'running',
                worker_id = $1,
                started_at = NOW()
            WHERE id = $2
        """, WORKER_ID, job_id)

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

            elif job["type"] == "process_report":
                from app.distributed.saga import execute_saga_job
                print("🎯 Calling saga executor...")
                result = await execute_saga_job(payload, conn)
                print("🎯 Saga returned: " + str(result))

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

            print("✅ Job " + str(job_id) + " completed! Result: " + str(result))

        except Exception as e:
            print("❌ Job " + str(job_id) + " failed: " + str(e))
            retries = job["retries"] + 1

            if retries < job["max_retries"]:
                print("🔁 Retrying job " + str(job_id))
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
                print("💀 Job " + str(job_id) + " permanently failed!")

async def main():
    from app.queue.redis_queue import pop_job

    print("🚀 Worker " + WORKER_ID + " starting...")

    db_pool = await connect_db()
    await wait_for_tables(db_pool)
    await register_worker(db_pool)

    asyncio.create_task(send_heartbeat(db_pool))

    print("👀 Worker " + WORKER_ID + " waiting for jobs...")

    while True:
        try:
            job_id = await pop_job()
            if job_id:
                await execute_job(job_id, db_pool)
        except Exception as e:
            print("❌ Worker error: " + str(e))
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())