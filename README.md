
# HNG14 Stage 2 DevOps — Job Processing System

A production-grade, containerised job processing system with a full CI/CD pipeline. Built as part of the HNG14 Stage 2 DevOps assessment.

---

## Architecture

The system is composed of three services that communicate via a shared Redis instance:

```
┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│   Frontend  │──────▶│     API     │──────▶│    Redis    │
│  (Node.js)  │        │  (FastAPI)  │        │             │
│  Port 3000  │        │  Port 8000  │        │  Port 6379  │
└─────────────┘        └─────────────┘        └─────────────┘
                                                      ▲
                                               ┌──────┴──────┐
                                               │   Worker    │
                                               │  (Python)   │
                                               └─────────────┘
```

| Service  | Stack | Responsibility |
|----------|-------|---------------|
| Frontend | Node.js / Express | Serves the UI, proxies job submission to the API |
| API | Python / FastAPI | Accepts jobs, stores state in Redis, exposes REST endpoints |
| Worker | Python | Polls the Redis queue, processes jobs, updates status to `completed` |
| Redis | Redis 7 | Shared message queue and job state store |

---

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for running tests locally)
- Node.js 20+ (for frontend development)

---

## Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/Adewumicrown/hng14-stage2-devops.git
cd hng14-stage2-devops
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env if needed — defaults work out of the box
```

### 3. Start the full stack

```bash
docker compose up --build
```

All four services will start. Check they are healthy:

```bash
docker compose ps
```

### 4. Use the application

| Endpoint | Method | Description |
|----------|--------|-------------|
| `http://localhost:3000` | GET | Frontend UI |
| `http://localhost:3000/submit` | POST | Submit a new job |
| `http://localhost:3000/status/:id` | GET | Check job status via frontend |
| `http://localhost:8000/health` | GET | API health check |
| `http://localhost:8000/jobs` | POST | Submit a job directly to API |
| `http://localhost:8000/jobs/:id` | GET | Get job status directly from API |

### 5. Submit a test job

```bash
# Submit a job
curl -X POST http://localhost:8000/jobs

# Poll its status (replace JOB_ID with the returned id)
curl http://localhost:8000/jobs/JOB_ID
```

---

## Running Tests

```bash
# Install dependencies
pip install pytest fakeredis fastapi httpx --break-system-packages

# Run from the repo root
pytest tests/test_api.py -v
```

All 7 tests use `fakeredis` — no real Redis instance is required.

| Test | Description |
|------|-------------|
| `test_create_job_returns_job_id` | POST /jobs returns a valid UUID |
| `test_create_job_sets_queued_status` | New jobs are set to `queued` in Redis |
| `test_create_job_pushes_to_queue` | Job ID is pushed onto the Redis queue |
| `test_get_job_returns_status` | GET /jobs/:id returns correct status |
| `test_get_nonexistent_job_returns_404` | Unknown job IDs return 404 |
| `test_health_check_returns_healthy` | /health returns `{"status": "healthy"}` |
| `test_multiple_jobs_are_independent` | Multiple jobs have unique IDs and statuses |

---

## CI/CD Pipeline

The GitHub Actions pipeline runs on every push and consists of 6 stages:

```
Lint ──▶ Test ──▶ Build & Push ──▶ Security Scan ──▶ Integration Test ──▶ Deploy
```

### Stage 1 — Lint

- **Python** (api, worker): `flake8` with `--max-line-length=120`
- **JavaScript** (frontend): `eslint@8` with `eslint:recommended`
- **Dockerfiles**: `hadolint` with `--failure-threshold error`

### Stage 2 — Test

- Runs all 7 pytest unit tests
- Redis mocked with `fakeredis` — no external dependencies required

### Stage 3 — Build & Push

- Multi-stage Docker builds for all 3 services
- Images pushed to Docker Hub with both `latest` and `git SHA` tags
- Build cache via GitHub Actions cache for faster rebuilds

### Stage 4 — Security Scan

- Trivy scans all 3 images for `CRITICAL` CVEs
- `--ignore-unfixed` skips vulnerabilities with no available patch
- SARIF reports uploaded as build artifacts

### Stage 5 — Integration Test

- Spins up the full stack with `docker compose`
- Submits a real job via the frontend proxy endpoint
- Polls until the worker marks the job as `completed`
- Tears down the stack after the test

### Stage 6 — Deploy (main branch only)

- SSHs into the EC2 instance via `appleboy/ssh-action`
- Pulls latest code with `git pull`
- Restarts all services with `docker compose up -d --build`
- Verifies the API is healthy before marking the deploy complete

---

## Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token (Read & Write) |
| `DEPLOY_HOST` | EC2 public IP or hostname |
| `DEPLOY_USER` | EC2 SSH username (typically `ubuntu`) |
| `DEPLOY_SSH_KEY` | EC2 private key (full PEM contents) |
| `DEPLOY_PATH` | Path to the repo on EC2, e.g. `/home/ubuntu/hng14-stage2-devops` |

---

## Docker Images

All images use multi-stage builds with the following security properties:

- Non-root user (`appuser`) for all services
- No secrets copied into the image
- `HEALTHCHECK` defined for all services
- CPU and memory limits set in `docker-compose.yml`
- Redis not exposed on the host network

| Image | Base | Size |
|-------|------|------|
| API | `python:3.11-slim` | ~150MB |
| Worker | `python:3.11-slim` | ~150MB |
| Frontend | `node:20-alpine` | ~120MB |

---

## Bug Fixes

22 bugs were identified and fixed from the original source. See [FIXES.md](./FIXES.md) for the full list. Key categories:

- Hardcoded `localhost` hostnames replaced with environment variables
- Missing signal handlers added to worker for graceful shutdown
- No error handling on Redis connection — retry logic with exponential backoff added
- Unpinned dependencies pinned in all `requirements.txt` files
- Module-level Redis connection replaced with lazy initialisation to support unit testing

---

## Project Structure

```
hng14-stage2-devops/
├── .github/
│   └── workflows/
│       └── pipeline.yml       # Full CI/CD pipeline
├── api/
│   ├── Dockerfile             # Multi-stage production build
│   ├── main.py                # FastAPI application
│   └── requirements.txt       # Pinned Python dependencies
├── frontend/
│   ├── Dockerfile             # Multi-stage production build
│   ├── app.js                 # Express application
│   ├── package.json
│   └── views/                 # Static HTML
├── worker/
│   ├── Dockerfile             # Multi-stage production build
│   ├── worker.py              # Job processing loop
│   └── requirements.txt       # Pinned Python dependencies
├── tests/
│   └── test_api.py            # 7 pytest unit tests
├── conftest.py
├── docker-compose.yml         # Full stack orchestration
├── .env.example               # Environment variable template
├── FIXES.md                   # Bug fix documentation
└── README.md
```

---

## License

This project was created for the HNG14 Stage 2 DevOps internship assessment.
