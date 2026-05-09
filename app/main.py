from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import os

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