# Distributed Fault-Tolerant Job Scheduler

A production-grade distributed job scheduling system built with Python and FastAPI.

## Live Demo
- Dashboard: https://job-scheduler-production-bf6b.up.railway.app/dashboard
- API Docs: https://job-scheduler-production-bf6b.up.railway.app/docs

## Architecture
- Saga Pattern → Multi-step job transactions with automatic rollback
- Circuit Breaker → Prevents cascading failures across services
- Priority Queue → Redis-based high/medium/low priority lanes
- Heartbeat Monitoring → Automatic worker failure detection
- API Key Auth → Secure job submission

## Tech Stack
- Python + FastAPI
- PostgreSQL
- Redis
- Docker + Docker Compose
- Railway (deployment)

## Features
- Real email sending via Gmail SMTP
- Real image resizing via Pillow
- Real PDF generation via ReportLab
- Live dashboard with real time updates
- Stress test with 30 simultaneous jobs
- Saga pattern demo with rollback
- Circuit breaker demo

## Run Locally

git clone https://github.com/krusta07/job-scheduler
cd job-scheduler
cp .env.example .env
docker-compose up --build

Visit http://localhost:8000/dashboard

## API Authentication
All job submissions require API key header:
x-api-key: your_api_key

## Job Types
- send_email → Sends real email via Gmail
- resize_image → Resizes image using Pillow
- generate_pdf → Generates PDF using ReportLab
- process_report → Multi-step Saga job (resize + PDF + email)