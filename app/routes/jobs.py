from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.db.postgres import get_db
import asyncpg

router = APIRouter(prefix="/jobs", tags=["Jobs"])

class JobCreate(BaseModel):
    type: str
    priority: str = "medium"
    payload: Optional[dict] = {}

@router.post("/", status_code=201)
async def create_job(
    job: JobCreate,
    db: asyncpg.Connection = Depends(get_db)
):
    allowed_types = ["send_email", "resize_image", "generate_pdf", "process_report"]
    if job.type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid job type. Allowed: " + str(allowed_types)
        )

    allowed_priorities = ["high", "medium", "low"]
    if job.priority not in allowed_priorities:
        raise HTTPException(
            status_code=400,
            detail="Invalid priority. Allowed: " + str(allowed_priorities)
        )

    import json
    from app.queue.redis_queue import push_job

    row = await db.fetchrow("""
        INSERT INTO jobs (type, priority, payload, status)
        VALUES ($1, $2, $3, 'pending')
        RETURNING id, type, status, priority,
                  payload, worker_id, retries, created_at
    """, job.type, job.priority, json.dumps(job.payload))

    await push_job(row["id"], job.priority)

    return {
        "message": "Job submitted successfully!",
        "job": {
            "id": row["id"],
            "type": row["type"],
            "status": row["status"],
            "priority": row["priority"],
            "created_at": str(row["created_at"])
        }
    }

@router.get("/")
async def list_jobs(
    status: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db)
):
    if status:
        rows = await db.fetch("""
            SELECT id, type, status, priority,
                   worker_id, retries, created_at, finished_at
            FROM jobs WHERE status = $1
            ORDER BY created_at DESC
        """, status)
    else:
        rows = await db.fetch("""
            SELECT id, type, status, priority,
                   worker_id, retries, created_at, finished_at
            FROM jobs ORDER BY created_at DESC
        """)

    return {
        "total": len(rows),
        "jobs": [
            {
                "id": row["id"],
                "type": row["type"],
                "status": row["status"],
                "priority": row["priority"],
                "worker_id": row["worker_id"],
                "retries": row["retries"],
                "created_at": str(row["created_at"]),
                "finished_at": str(row["finished_at"]) if row["finished_at"] else None
            }
            for row in rows
        ]
    }

@router.get("/workers/status")
async def get_workers(
    db: asyncpg.Connection = Depends(get_db)
):
    rows = await db.fetch("""
        SELECT id, status, last_seen,
               jobs_completed, registered_at
        FROM workers ORDER BY id
    """)
    return {
        "total_workers": len(rows),
        "workers": [
            {
                "id": row["id"],
                "status": row["status"],
                "last_seen": str(row["last_seen"]),
                "jobs_completed": row["jobs_completed"]
            }
            for row in rows
        ]
    }

@router.get("/breakers/status")
async def get_breaker_status():
    from app.distributed.circuit_breaker import email_breaker, image_breaker, pdf_breaker
    return {
        "breakers": {
            "email": email_breaker.get_status(),
            "image": image_breaker.get_status(),
            "pdf": pdf_breaker.get_status()
        }
    }

@router.get("/{job_id}")
async def get_job(
    job_id: int,
    db: asyncpg.Connection = Depends(get_db)
):
    row = await db.fetchrow("""
        SELECT * FROM jobs WHERE id = $1
    """, job_id)

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Job " + str(job_id) + " not found"
        )

    return {
        "id": row["id"],
        "type": row["type"],
        "status": row["status"],
        "priority": row["priority"],
        "payload": row["payload"],
        "worker_id": row["worker_id"],
        "retries": row["retries"],
        "result": row["result"],
        "error": row["error"],
        "created_at": str(row["created_at"]),
        "started_at": str(row["started_at"]) if row["started_at"] else None,
        "finished_at": str(row["finished_at"]) if row["finished_at"] else None
    }

@router.delete("/{job_id}")
async def cancel_job(
    job_id: int,
    db: asyncpg.Connection = Depends(get_db)
):
    row = await db.fetchrow("""
        SELECT id, status FROM jobs WHERE id = $1
    """, job_id)

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Job " + str(job_id) + " not found"
        )

    if row["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel job with status " + row["status"]
        )

    await db.execute("""
        UPDATE jobs SET status = 'cancelled' WHERE id = $1
    """, job_id)

    return {"message": "Job " + str(job_id) + " cancelled successfully!"}