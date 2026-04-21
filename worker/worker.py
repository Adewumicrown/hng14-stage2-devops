import redis
import time
import os
import signal
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

running = True


def handle_shutdown(signum, frame):
    """Gracefully handle SIGTERM and SIGINT."""
    global running
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    running = False


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


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


def process_job(r, job_id):
    logger.info(f"Processing job {job_id}")
    r.hset(f"job:{job_id}", "status", "processing")
    time.sleep(2)  # simulate work
    r.hset(f"job:{job_id}", "status", "completed")
    logger.info(f"Done: {job_id}")


def main():
    r = get_redis_client()
    logger.info("Worker started, waiting for jobs...")

    while running:
        try:
            job = r.brpop("jobs", timeout=5)
            if job:
                _, job_id = job
                process_job(r, job_id)
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Redis connection lost: {e}. Retrying in 5s...")
            time.sleep(5)
            try:
                r = get_redis_client()
            except RuntimeError:
                logger.critical("Could not reconnect to Redis. Exiting.")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error processing job: {e}")

    logger.info("Worker shut down cleanly.")


if __name__ == "__main__":
    main()
