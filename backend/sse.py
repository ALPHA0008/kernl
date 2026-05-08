import asyncio
import json
from typing import Dict, AsyncGenerator

class CompilationEventBus:
    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}

    def get_queue(self, job_id: str) -> asyncio.Queue:
        if job_id not in self.queues:
            self.queues[job_id] = asyncio.Queue()
        return self.queues[job_id]

    async def emit_event(self, job_id: str, event_type: str, data: dict):
        queue = self.get_queue(job_id)
        await queue.put({"type": event_type, "data": data})

    async def event_generator(self, job_id: str) -> AsyncGenerator[str, None]:
        """Yields SSE-formatted strings. Uses unnamed events so the
        frontend's EventSource.onmessage handler fires correctly.
        Payload: data: {"event": "<type>", "data": {<payload>}}\n\n
        """
        queue = self.get_queue(job_id)
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=300)
                payload = json.dumps({"event": event["type"], "data": event["data"]})
                yield f"data: {payload}\n\n"
                if event["type"] in ["pipeline_complete", "pipeline_error"]:
                    break
        except asyncio.TimeoutError:
            yield f'data: {json.dumps({"event": "timeout", "data": {}})}\n\n'
        finally:
            if job_id in self.queues:
                del self.queues[job_id]

event_bus = CompilationEventBus()

async def emit(job_id: str, event_type: str, data: dict):
    await event_bus.emit_event(job_id, event_type, data)
