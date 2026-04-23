from fastapi import FastAPI, HTTPException
import redis
import uuid
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

def get_redis_client():
    """Create Redis client with retry logic."""
    redis_host = os.environ.get("REDIS_HOST", "redis")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    retries = 5
    for attempt in range(retries):
        try:
            client = redis.Redis(
                host=redis_host,
                port=redis_port,
                socket_connect_timeout=5,
                decode_responses=True,
            )
            client.ping()
            logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
            return client
        except redis.exceptions.ConnectionError as e:
            logger.warning(f"Redis connection attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError("Could not connect to Redis after multiple attempts")

r = None

def get_redis():
    global r
    if r is None:
        r = get_redis_client()
    return r

@app.get("/health")
def health_check():
    try:
        get_redis().ping()
        return {"status": "healthy"}
    except Exception:
        raise HTTPException(status_code=503, detail="Redis unavailable")

@app.post("/jobs")
def create_job():
    job_id = str(uuid.uuid4())
    get_redis().lpush("jobs", job_id)
    get_redis().hset(f"job:{job_id}", "status", "queued")
    logger.info(f"Created job {job_id}")
    return {"job_id": job_id}

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    status = get_redis().hget(f"job:{job_id}", "status")
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "status": status}
