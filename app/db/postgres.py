import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        print("🔌 Connecting to database...")
        _pool = await asyncpg.create_pool(
            dsn=os.getenv("DATABASE_URL"),
            min_size=2,
            max_size=10
        )
        print("✅ Database connected!")
    return _pool

async def get_db():
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection

async def create_tables():
    print("📋 Creating tables...")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          SERIAL PRIMARY KEY,
                type        VARCHAR(50) NOT NULL,
                status      VARCHAR(20) DEFAULT 'pending',
                priority    VARCHAR(10) DEFAULT 'medium',
                payload     JSONB,
                worker_id   VARCHAR(50),
                retries     INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                result      TEXT,
                error       TEXT,
                created_at  TIMESTAMP DEFAULT NOW(),
                started_at  TIMESTAMP,
                finished_at TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id             VARCHAR(50) PRIMARY KEY,
                status         VARCHAR(20) DEFAULT 'online',
                last_seen      TIMESTAMP DEFAULT NOW(),
                jobs_completed INTEGER DEFAULT 0,
                registered_at  TIMESTAMP DEFAULT NOW()
            )
        """)
        print("✅ Database tables created!")