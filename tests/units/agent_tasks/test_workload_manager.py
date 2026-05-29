import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.agent_tasks.workload_manager import WorkloadManager, multiplex_generators

# Dummy worker function for testing
async def dummy_worker(metadata):
    file_id = metadata.get("id")
    yield {"status": f"Processing {file_id}"}
    await asyncio.sleep(0.01)  # yield control
    yield {"result": {"id": file_id, "status": "success"}}

@pytest.mark.asyncio
async def test_workload_manager_should_divide_default():
    manager = WorkloadManager(worker_fn=dummy_worker)
    
    # 1. 1 file, small size -> False
    assert manager._should_divide([{"page_count": 1, "size_bytes": 100}]) is False
    
    # 2. 8 files -> True
    assert manager._should_divide([{"page_count": 1, "size_bytes": 100}] * 8) is True
    
    # 3. 1 file, 10MB -> True
    assert manager._should_divide([{"page_count": 1, "size_bytes": 10 * 1024 * 1024}]) is True
    
    # 4. 1 file, 8 pages -> True
    assert manager._should_divide([{"page_count": 8, "size_bytes": 100}]) is True


@pytest.mark.asyncio
async def test_workload_manager_process_batch_fast_path():
    manager = WorkloadManager(worker_fn=dummy_worker)
    files = [
        {"id": "file-1", "page_count": 1, "size_bytes": 1024},
        {"id": "file-2", "page_count": 1, "size_bytes": 1024}
    ]
    
    results = await manager.process_batch(files)
    
    assert len(results) == 2
    assert results[0] == {"id": "file-1", "status": "success"}
    assert results[1] == {"id": "file-2", "status": "success"}


@pytest.mark.asyncio
async def test_workload_manager_process_batch_slow_path(monkeypatch):
    manager = WorkloadManager(worker_fn=dummy_worker)
    # Mock asyncio.sleep to check rate limit bumpers
    sleep_calls = []
    async def mock_sleep(delay):
        sleep_calls.append(delay)
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)
    
    # 8 files forces slow-path chunking (chunk size 4)
    files = [{"id": f"file-{i}", "page_count": 1, "size_bytes": 100} for i in range(8)]
    
    results = await manager.process_batch(files)
    
    assert len(results) == 8
    # Filter sleep calls to only count the rate-limit bumper sleeps (which are 1 second)
    rate_limit_sleeps = [s for s in sleep_calls if s == 1]
    assert len(rate_limit_sleeps) == 2
    assert rate_limit_sleeps == [1, 1]


@pytest.mark.asyncio
async def test_workload_manager_process_batch_stream_happy_path():
    manager = WorkloadManager(worker_fn=dummy_worker)
    files = [
        {"id": "file-1", "page_count": 1, "size_bytes": 1024},
        {"id": "file-2", "page_count": 1, "size_bytes": 1024}
    ]
    
    events = []
    async for event in manager.process_batch_stream(files):
        events.append(event)
        
    # We expect status and result events for each file
    assert len(events) == 4
    statuses = [e["status"] for e in events if "status" in e]
    results = [e["result"] for e in events if "result" in e]
    
    assert "Processing file-1" in statuses
    assert "Processing file-2" in statuses
    assert {"id": "file-1", "status": "success"} in results
    assert {"id": "file-2", "status": "success"} in results


@pytest.mark.asyncio
async def test_multiplex_generators_merges_all_streams():
    async def gen1():
        yield 1
        yield 2
        
    async def gen2():
        yield 3
        yield 4
        
    items = []
    async for item in multiplex_generators(gen1(), gen2()):
        items.append(item)
        
    assert len(items) == 4
    assert set(items) == {1, 2, 3, 4}
