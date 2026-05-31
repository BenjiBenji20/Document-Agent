import asyncio
import typing


async def multiplex_generators(*generators) -> typing.AsyncGenerator[dict, None]:
    queue = asyncio.Queue()

    async def worker(gen):
        async for item in gen:
            await queue.put(item)

    async def run_all():
        await asyncio.gather(*[worker(gen) for gen in generators])
        await queue.put(None)

    task = asyncio.create_task(run_all())

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class WorkloadManager:
    CHUNK_SIZE = 4
    WINDOW_SECONDS = 60

    def __init__(self, worker_fn):
        self.worker_fn = worker_fn

    def _should_divide(self, files: list[dict]) -> bool:
        if len(files) > self.CHUNK_SIZE:
            return True
        total_pages = sum(f.get("page_count", 0) for f in files)
        total_size_mb = sum(f.get("size_bytes", 0) for f in files) / (1024 * 1024)
        if total_pages >= 8 or total_size_mb >= 10:
            return True
        return False

    def _chunk_workload(self, files: list[dict]) -> list[list[dict]]:
        return [
            files[i:i + self.CHUNK_SIZE]
            for i in range(0, len(files), self.CHUNK_SIZE)
        ]

    def _exception_fallback(self, file_meta: dict, exc: Exception) -> dict:
        return {
            "id": file_meta.get("id", "unknown"),
            "file_name": file_meta.get("file_name", "unknown"),
            "status": "failed",
            "error": str(exc)
        }

    async def _run_worker(self, f: dict) -> dict:
        result = None
        async for event in self.worker_fn(f):
            if "result" in event:
                result = event["result"]
        return result

    async def _run_chunk(self, chunk: list[dict]) -> list[dict]:
        tasks = [self._run_worker(f) for f in chunk]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [
            r if not isinstance(r, Exception)
            else self._exception_fallback(chunk[i], r)
            for i, r in enumerate(results)
        ]

    async def process_batch(self, files: list[dict]) -> list[dict]:
        if not self._should_divide(files):
            return await self._run_chunk(files)

        chunks = self._chunk_workload(files)
        final_results = []
        loop = asyncio.get_event_loop()

        for i, chunk in enumerate(chunks):
            start = loop.time()
            results = await self._run_chunk(chunk)
            final_results.extend(results)

            if i < len(chunks) - 1:
                elapsed = loop.time() - start
                wait = max(0, self.WINDOW_SECONDS - elapsed)
                if wait > 0:
                    await asyncio.sleep(wait)

        return final_results

    async def process_batch_stream(
        self, files: list[dict]
    ) -> typing.AsyncGenerator[dict, None]:
        if not self._should_divide(files):
            generators = [self.worker_fn(f) for f in files]
            async for event in multiplex_generators(*generators):
                yield event
            return

        chunks = self._chunk_workload(files)
        loop = asyncio.get_event_loop()

        for i, chunk in enumerate(chunks):
            start = loop.time()
            generators = [self.worker_fn(f) for f in chunk]
            async for event in multiplex_generators(*generators):
                yield event

            if i < len(chunks) - 1:
                elapsed = loop.time() - start
                wait = max(0, self.WINDOW_SECONDS - elapsed)
                if wait > 0:
                    await asyncio.sleep(wait)
                    