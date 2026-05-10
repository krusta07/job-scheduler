from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import os
import json

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.postgres import create_tables
    print("🚀 App starting up...")
    await create_tables()
    yield
    print("👋 Shutting down...")

app = FastAPI(
    title="Distributed Job Scheduler",
    description="Fault tolerant job scheduler with Saga and Circuit Breaker",
    version="1.0.0",
    lifespan=lifespan
)

from app.routes.jobs import router as jobs_router
app.include_router(jobs_router)

app.mount("/static", StaticFiles(directory="app/dashboard"), name="static")

@app.get("/dashboard")
async def dashboard():
    return FileResponse("app/dashboard/index.html")

@app.get("/queue/lengths")
async def queue_lengths():
    from app.queue.redis_queue import get_queue_lengths
    return await get_queue_lengths()

@app.get("/")
async def root():
    return {"message": "Welcome to Distributed Job Scheduler!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "worker_id": os.getenv("WORKER_ID", "unknown")}

@app.get("/demo/stress-test")
async def stress_test():
    from app.db.postgres import get_pool
    from app.queue.redis_queue import push_job

    pool = await get_pool()
    submitted = []

    job_types = [
        {
            "type": "send_email",
            "payload": {
                "email": "prathamverma1234.pv@gmail.com",
                "subject": "Stress Test Email!",
                "body": "This is a stress test email!"
            }
        },
        {
            "type": "resize_image",
            "payload": {
                "filename": "test.jpg",
                "width": 300,
                "height": 300
            }
        },
        {
            "type": "generate_pdf",
            "payload": {
                "title": "Stress Test Report",
                "content": "Generated during stress test!"
            }
        }
    ]

    async with pool.acquire() as conn:
        for i in range(10):
            for job_def in job_types:
                priority = "high" if i < 3 else "medium" if i < 7 else "low"
                row = await conn.fetchrow("""
                    INSERT INTO jobs (type, priority, payload, status)
                    VALUES ($1, $2, $3, 'pending')
                    RETURNING id, type, priority
                """, job_def["type"], priority, json.dumps(job_def["payload"]))

                await push_job(row["id"], priority)
                submitted.append({
                    "id": row["id"],
                    "type": row["type"],
                    "priority": row["priority"]
                })

    return {
        "message": "Stress test started!",
        "total_jobs_submitted": len(submitted),
        "breakdown": {
            "email_jobs": 10,
            "image_jobs": 10,
            "pdf_jobs": 10
        }
    }

@app.get("/demo/saga-test")
async def saga_test():
    from app.db.postgres import get_pool
    from app.queue.redis_queue import push_job

    pool = await get_pool()
    submitted = []

    async with pool.acquire() as conn:
        for i in range(5):
            row = await conn.fetchrow("""
                INSERT INTO jobs (type, priority, payload, status)
                VALUES ($1, $2, $3, 'pending')
                RETURNING id, type, priority
            """, "process_report", "high", json.dumps({
                "filename": "test.jpg",
                "email": "prathamverma1234.pv@gmail.com",
                "title": "Saga Report " + str(i+1)
            }))

            await push_job(row["id"], "high")
            submitted.append({"id": row["id"], "type": "process_report"})

    return {
        "message": "Saga test started!",
        "total_jobs": len(submitted),
        "each_job_steps": ["resize_image", "generate_pdf", "send_email"]
    }

@app.get("/demo/circuit-breaker-test")
async def circuit_breaker_test():
    from app.distributed.circuit_breaker import email_breaker, image_breaker, pdf_breaker
    return {
        "message": "Circuit Breaker Status",
        "breakers": {
            "email": email_breaker.get_status(),
            "image": image_breaker.get_status(),
            "pdf": pdf_breaker.get_status()
        }
    }