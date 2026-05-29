import asyncio
import typing

async def multiplex_generators(*generators) -> typing.AsyncGenerator[dict, None]:
    queue = asyncio.Queue()
    finished = 0

    async def worker(gen):
        nonlocal finished
        try:
            async for item in gen:
                await queue.put(item)
        finally:
            finished += 1
            if finished == len(generators):
                await queue.put(None)

    for gen in generators:
        asyncio.create_task(worker(gen))

    while True:
        item = await queue.get()
        if item is None:
            break
        yield item


class WorkloadManager:
    def __init__(self, worker_fn):
        """
        Accepts any asynchronous coroutine/generator function that processes a single file.
        Signature expected: worker_fn(file_meta: dict)
        """
        self.worker_fn = worker_fn

    def _should_divide(self, files: list[dict]) -> bool:
        """Evaluates batch inputs against performance thresholds."""
        if len(files) >= 8:
            return True
            
        total_pages = sum(f.get("page_count", 0) for f in files)
        total_size_mb = sum(f.get("size_bytes", 0) for f in files) / (1024 * 1024)
        
        if total_pages >= 8 or total_size_mb >= 10:
            return True
            
        return False

    def _chunk_workload(self, files: list[dict], chunk_size: int = 4) -> list[list[dict]]:
        """Splits a batch into smaller worker-friendly groups."""
        return [files[i:i + chunk_size] for i in range(0, len(files), chunk_size)]

    async def _run_worker(self, f: dict) -> dict:
        """Drains the async generator from worker_fn and returns the final result dict."""
        result = None
        async for event in self.worker_fn(f):
            if "result" in event:
                result = event["result"]
        return result

    async def process_batch(self, files: list[dict]) -> list[dict]:
        """Coordinates execution, handling division of labor automatically and blindly."""
        if not self._should_divide(files):
            # Fast-path: Execute all tasks concurrently in one small burst
            tasks = [self._run_worker(f) for f in files]
            return await asyncio.gather(*tasks)

        # Slow-path: Split labor across parallel worker pools to protect rate limits
        chunks = self._chunk_workload(files, chunk_size=4)
        final_results = []
        
        for chunk in chunks:
            # Execute this specific chunk block in parallel
            tasks = [self._run_worker(f) for f in chunk]
            chunk_results = await asyncio.gather(*tasks)
            final_results.extend(chunk_results)
            
            # Rate-limit safety bumper for free tiers
            await asyncio.sleep(1) 
            
        return final_results

    async def process_batch_stream(self, files: list[dict]) -> typing.AsyncGenerator[dict, None]:
        """Coordinates execution, yielding progress and results concurrently as they complete."""
        if not self._should_divide(files):
            generators = [self.worker_fn(f) for f in files]
            async for event in multiplex_generators(*generators):
                yield event
        else:
            chunks = self._chunk_workload(files, chunk_size=4)
            for chunk in chunks:
                generators = [self.worker_fn(f) for f in chunk]
                async for event in multiplex_generators(*generators):
                    yield event
                await asyncio.sleep(1)
    