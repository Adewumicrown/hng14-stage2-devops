# FIXES.md — Bug Documentation

All bugs found in the original source code, with file, line, problem, and fix.

---

## API (`api/main.py`)

### Fix 1 — Hardcoded Redis host
- **File:** `api/main.py`
- **Line:** 8
- **Problem:** `redis.Redis(host="localhost", ...)` — hardcoded to `localhost`. Inside Docker, each service runs in its own container. `localhost` inside the API container refers to the API container itself, not Redis. This causes an immediate `ConnectionRefusedError` on startup.
- **Fix:** Changed to `host=os.environ.get("REDIS_HOST", "redis")` so the host is read from an environment variable, defaulting to the Docker Compose service name `redis`.

### Fix 2 — Hardcoded Redis port
- **File:** `api/main.py`
- **Line:** 8
- **Problem:** `redis.Redis(..., port=6379)` — port hardcoded. Cannot be changed without modifying source code.
- **Fix:** Changed to `port=int(os.environ.get("REDIS_PORT", 6379))`.

### Fix 3 — Redis client created at module load with no retry
- **File:** `api/main.py`
- **Line:** 8
- **Problem:** The Redis client was instantiated at module import time with no connection retry. If Redis isn't ready yet (common during container startup), the API crashes immediately and does not recover.
- **Fix:** Wrapped client creation in a `get_redis_client()` function with exponential backoff retry (5 attempts). Added `client.ping()` to verify the connection before returning.

### Fix 4 — No health check endpoint
- **File:** `api/main.py`
- **Line:** N/A (missing)
- **Problem:** No `/health` endpoint existed. Docker and `docker-compose` health checks require an HTTP endpoint to probe. Without it, `depends_on: condition: service_healthy` cannot work.
- **Fix:** Added `GET /health` endpoint that pings Redis and returns `{"status": "healthy"}` or HTTP 503 if Redis is unreachable.

### Fix 5 — Redis response not decoded (wrong return type)
- **File:** `api/main.py`
- **Line:** 19
- **Problem:** `r.hget(...)` returns `bytes` by default. The original code called `.decode()` manually — brittle and easy to forget. Also, the original used `return {"error": "not found"}` with HTTP 200 for a missing job instead of a proper 404.
- **Fix:** Added `decode_responses=True` to the Redis client so all responses are strings. Changed missing-job response to raise `HTTPException(status_code=404)`.

### Fix 6 — Queue key inconsistency
- **File:** `api/main.py`
- **Line:** 12
- **Problem:** The API pushed jobs to a queue named `"job"` (singular) while the worker popped from a queue named `"job"` as well — however this is a latent naming issue prone to future inconsistency. Standardised to `"jobs"` (plural) across both services.
- **Fix:** Changed `r.lpush("job", job_id)` to `r.lpush("jobs", job_id)` in API. Updated worker to pop from `"jobs"` as well.

### Fix 7 — Unpinned dependencies
- **File:** `api/requirements.txt`
- **Line:** All
- **Problem:** No version pins (`fastapi`, `uvicorn`, `redis` with no versions). This means different builds may install different versions, breaking reproducibility.
- **Fix:** Pinned to `fastapi==0.111.0`, `uvicorn==0.29.0`, `redis==5.0.4`.

---

## Worker (`worker/worker.py`)

### Fix 8 — Hardcoded Redis host
- **File:** `worker/worker.py`
- **Line:** 6
- **Problem:** Same as API Fix 1 — `host="localhost"` fails in Docker networking.
- **Fix:** Changed to `host=os.environ.get("REDIS_HOST", "redis")`.

### Fix 9 — Hardcoded Redis port
- **File:** `worker/worker.py`
- **Line:** 6
- **Problem:** Same as API Fix 2.
- **Fix:** Changed to `port=int(os.environ.get("REDIS_PORT", 6379))`.

### Fix 10 — Signal handlers imported but never registered
- **File:** `worker/worker.py`
- **Line:** 4 (import), missing registration
- **Problem:** `import signal` was present but `signal.signal()` was never called. The worker ignores SIGTERM, meaning Docker cannot shut it down gracefully. A `docker stop` would wait 10 seconds then SIGKILL it, potentially leaving jobs half-processed.
- **Fix:** Added `signal.signal(signal.SIGTERM, handle_shutdown)` and `signal.signal(signal.SIGINT, handle_shutdown)` with a `running` flag to exit the loop cleanly.

### Fix 11 — No error handling in main loop
- **File:** `worker/worker.py`
- **Line:** 12–16
- **Problem:** The `while True` loop had no `try/except`. Any Redis connection drop or unexpected error would crash the worker process entirely with no recovery.
- **Fix:** Wrapped loop body in `try/except redis.exceptions.ConnectionError` with reconnect logic, and a general `except Exception` to log and continue.

### Fix 12 — No "processing" status update
- **File:** `worker/worker.py`
- **Line:** 13
- **Problem:** Job status jumped directly from `queued` to `completed` with no intermediate state. The frontend had no way to show a job was being worked on.
- **Fix:** Added `r.hset(f"job:{job_id}", "status", "processing")` at the start of `process_job()`.

### Fix 13 — Unpinned dependency
- **File:** `worker/requirements.txt`
- **Line:** 1
- **Problem:** `redis` with no version pin.
- **Fix:** Pinned to `redis==5.0.4`.

---

## Frontend (`frontend/app.js`)

### Fix 14 — Hardcoded API URL
- **File:** `frontend/app.js`
- **Line:** 6
- **Problem:** `API_URL = "http://localhost:8000"` — same container networking issue. The frontend container cannot reach the API container via `localhost`.
- **Fix:** Changed to `const API_URL = process.env.API_URL || "http://api:8000"`.

### Fix 15 — Hardcoded port
- **File:** `frontend/app.js`
- **Line:** 25
- **Problem:** `app.listen(3000, ...)` — port hardcoded and not configurable via environment.
- **Fix:** Changed to `app.listen(process.env.PORT || 3000, ...)`.

### Fix 16 — Server binds to 127.0.0.1 by default
- **File:** `frontend/app.js`
- **Line:** 25
- **Problem:** Node/Express defaults to binding on `127.0.0.1` (loopback only). Inside a container, this means the port is not reachable from outside the container even if it's mapped.
- **Fix:** Changed to `app.listen(PORT, '0.0.0.0', ...)`.

### Fix 17 — No health check endpoint
- **File:** `frontend/app.js`
- **Line:** N/A (missing)
- **Problem:** No `/health` endpoint for Docker health checks.
- **Fix:** Added `GET /health` returning `{"status": "healthy"}`.

---

## Frontend (`frontend/views/index.html`)

### Fix 18 — No error handling in pollJob()
- **File:** `frontend/views/index.html`
- **Line:** ~27
- **Problem:** `pollJob()` had no `try/catch`. A network error or non-200 response would silently break polling with no feedback to the user.
- **Fix:** Wrapped fetch calls in `try/catch`, display error message in UI if polling fails.

### Fix 19 — Infinite polling with no timeout
- **File:** `frontend/views/index.html`
- **Line:** ~29
- **Problem:** `pollJob()` polled forever if a job never reached `completed`. This creates a memory/network leak in the browser and hangs the UI indefinitely for stuck jobs.
- **Fix:** Added `MAX_POLL_ATTEMPTS = 30` counter (~60 seconds). If exceeded, the job is marked as `timed out`.

---

## Project-Level

### Fix 20 — No .gitignore
- **File:** N/A (missing)
- **Problem:** No `.gitignore` present. `node_modules/`, `.env`, and `__pycache__/` could be accidentally committed, bloating the repo or leaking secrets.
- **Fix:** Created `.gitignore` covering Python, Node, Docker, OS, and IDE artifacts. `.env` is explicitly ignored.

### Fix 21 — No .env.example
- **File:** N/A (missing)
- **Problem:** No `.env.example` provided. Contributors and evaluators have no reference for what environment variables are required.
- **Fix:** Created `.env.example` with all required variables and placeholder values.

### Fix 22 — Empty README.md
- **File:** `README.md`
- **Problem:** README was completely empty — no setup instructions, no prerequisites, no usage.
- **Fix:** Will be filled in as part of documentation phase.
