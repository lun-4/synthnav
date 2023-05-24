import inspect
import asyncio
import logging
import threading
import queue
from typing import Any
from dataclasses import dataclass
from uuid import UUID, uuid4

log = logging.getLogger(__name__)


class ConnectionID(UUID):
    pass


class ProcessID(UUID):
    pass


@dataclass
class Callback:
    originating_thread_name: str
    function: Any


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
            self.callbacks[as_pid] = Callback(threading.current_thread().name, callback)
        asyncio.run_coroutine_threadsafe(
            spawner(self, function, args, kwargs, as_pid), self.loop
        )
        return as_pid

    def send(self, process_id: ProcessID, data):
        callback = self.callbacks.get(process_id)
        if not callback:
            log.warning("unknown pid %r", process_id)
            return

        current_thread_name = threading.current_thread().name

        if (
            current_thread_name == "asyncio"
            and callback.originating_thread_name == "asyncio"
        ):
            # async-to-async, just await the callback
            asyncio.run(callback.function(process_id, data))
            return

        if callback.originating_thread_name == "asyncio":
            # callback is from asyncio, schedule it to the loop
            asyncio.run_coroutine_threadsafe(
                spawn_task(callback.function, process_id, data), self.loop
            )
        else:
            # callback is from tk thread, push to it
            self.sync_queue.put((callback.function, [process_id, data]))
            self.sync_message_notifier()

    def finish(self, id: UUID):
        self.callbacks.pop(id, None)
