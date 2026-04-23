"""
Unit tests for the API service.
Redis is mocked using fakeredis — no real Redis required.
"""
import pytest
import fakeredis
from fastapi.testclient import TestClient
from unittest.mock import patch

# Pre-import the module BEFORE any fixture runs, with get_redis_client patched
# so the module-level r = None line doesn't try to connect
import api.main  # noqa: E402

@pytest.fixture(autouse=True)
def mock_redis():
    fake = fakeredis.FakeRedis(decode_responses=True)
    with patch("api.main.get_redis", return_value=fake), \
         patch("api.main.r", fake):
        yield fake

@pytest.fixture()
def client(mock_redis):
    return TestClient(api.main.app)

# ---------------------------------------------------------------------------
# Test 1: POST /jobs creates a job and returns a job_id
# ---------------------------------------------------------------------------
def test_create_job_returns_job_id(client, mock_redis):
    response = client.post("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert len(data["job_id"]) == 36  # UUID format

# ---------------------------------------------------------------------------
# Test 2: POST /jobs sets status to "queued" in Redis
# ---------------------------------------------------------------------------
def test_create_job_sets_queued_status(client, mock_redis):
    response = client.post("/jobs")
    job_id = response.json()["job_id"]
    status = mock_redis.hget(f"job:{job_id}", "status")
    assert status == "queued"

# ---------------------------------------------------------------------------
# Test 3: POST /jobs pushes job_id onto the "jobs" queue
# ---------------------------------------------------------------------------
def test_create_job_pushes_to_queue(client, mock_redis):
    response = client.post("/jobs")
    job_id = response.json()["job_id"]
    queue_contents = mock_redis.lrange("jobs", 0, -1)
    assert job_id in queue_contents

# ---------------------------------------------------------------------------
# Test 4: GET /jobs/{job_id} returns correct status
# ---------------------------------------------------------------------------
def test_get_job_returns_status(client, mock_redis):
    create_resp = client.post("/jobs")
    job_id = create_resp.json()["job_id"]
    get_resp = client.get(f"/jobs/{job_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "queued"

# ---------------------------------------------------------------------------
# Test 5: GET /jobs/{job_id} returns 404 for unknown job
# ---------------------------------------------------------------------------
def test_get_nonexistent_job_returns_404(client, mock_redis):
    response = client.get("/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

# ---------------------------------------------------------------------------
# Test 6: GET /health returns healthy when Redis is reachable
# ---------------------------------------------------------------------------
def test_health_check_returns_healthy(client, mock_redis):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

# ---------------------------------------------------------------------------
# Test 7: Multiple jobs are independent
# ---------------------------------------------------------------------------
def test_multiple_jobs_are_independent(client, mock_redis):
    id1 = client.post("/jobs").json()["job_id"]
    id2 = client.post("/jobs").json()["job_id"]
    assert id1 != id2
    status1 = client.get(f"/jobs/{id1}").json()["status"]
    status2 = client.get(f"/jobs/{id2}").json()["status"]
    assert status1 == "queued"
    assert status2 == "queued"
