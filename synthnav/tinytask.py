import inspect
import asyncio
import logging
import queue
from uuid import UUID, uuid4

log = logging.getLogger(__name__)


class ConnectionID(UUID):
    pass


class ProcessID(UUID):
    pass


async def spawner(tt, function, args, kwargs, reply_to):
    try:
        coroutine = function(tt, *args, **kwargs, from_pid=reply_to)
        asyncio.create_task(coroutine)
    except:
        log.exception("shit")


async def spawn_task(coro):
    asyncio.create_task(coro)


class TinytaskManager:
    def __init__(self, loop, sync_message_notifier):
        self.loop = loop
        self.callbacks = {}
        self.sync_message_notifier = sync_message_notifier
        self.sync_queue = queue.Queue()

    def spawn_once(
        self,
        function,
        callback=None,
        *,
        args=None,
        kwargs=None,
        as_pid: UUID = None,
    ) -> ConnectionID:
        args = args or []
        kwargs = kwargs or {}

        as_pid = as_pid or uuid4()
        if callback:
            self.callbacks[as_pid] = callback
        asyncio.run_coroutine_threadsafe(
            spawner(self, function, args, kwargs, as_pid), self.loop
        )
        return as_pid

    def send(self, process_id: ProcessID, data):
        callback = self.callbacks.get(process_id)
        if not callback:
            log.warning("unknown pid %r", process_id)
            return
        if inspect.iscoroutinefunction(callback):
            asyncio.run_coroutine_threadsafe(
                spawn_task(callback, process_id, data), self.loop
            )
        else:
            # push to tk
            self.sync_queue.put((callback, [process_id, data]))
            self.sync_message_notifier()

    def finish(self, id: UUID):
        self.callbacks.pop(id, None)
