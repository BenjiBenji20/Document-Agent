import asyncio

class WorkloadManager:
    def __init__(self, worker_fn):
        """
        Accepts any asynchronous coroutine function that processes a single file.
        Signature expected: worker_fn(gcs_url: str, file_meta: dict) -> dict
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

    async def process_batch(self, files: list[dict]) -> list[dict]:
        """Coordinates execution, handling division of labor automatically and blindly."""
        if not self._should_divide(files):
            # Fast-path: Execute all tasks concurrently in one small burst
            tasks = [self.worker_fn(f) for f in files]
            return await asyncio.gather(*tasks)

        # Slow-path: Split labor across parallel worker pools to protect rate limits
        chunks = self._chunk_workload(files, chunk_size=4)
        final_results = []
        
        for chunk in chunks:
            # Execute this specific chunk block in parallel
            tasks = [self.worker_fn(f) for f in chunk]
            chunk_results = await asyncio.gather(*tasks)
            final_results.extend(chunk_results)
            
            # Rate-limit safety bumper for free tiers
            await asyncio.sleep(1) 
            
        return final_results
    