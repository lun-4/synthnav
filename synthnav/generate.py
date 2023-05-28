import asyncio
import json
import random
import logging
import string
import os
import websockets
import random
import dataclasses
from typing import Generator
from .config import GenerationSettings
from .tinytask import producer

log = logging.getLogger(__name__)

GENERATION_LOCK = asyncio.Lock()


async def generate_text(
    input_prompt: str, *, settings: GenerationSettings, seed=-1
) -> Generator[str, None, None]:
    """From a given input prompt, spit out the tokens that compose the
    textual completion of that prompt."""

    if seed == -1:
        seed = random.randint(1, 2**31)

    server = os.environ["SERVER_ADDR"]
    request = {
        **{
            "prompt": input_prompt,
            "seed": seed,
        },
        **dataclasses.asdict(settings),
    }
    url = f"ws://{server}/api/v1/stream"

    result = input_prompt

    async with GENERATION_LOCK:
        log.debug("connecting to %r", url)
        async with websockets.connect(url) as websocket:
            log.debug("connected to %r", url)
            await websocket.send(json.dumps(request))

            while True:
                incoming_data = await websocket.recv()
                incoming_data = json.loads(incoming_data)

                match incoming_data["event"]:
                    case "text_stream":
                        content = incoming_data["text"]
                        log.debug("got %r", content)
                        yield content
                    case "stream_end":
                        return

    log.debug("reached end of stream, returning")


@producer
async def text_generator_process(tt, settings, prompt, from_pid):
    async for data in generate_text(prompt, settings=settings):
        tt.send(from_pid, ("new_incoming_token", data))
    tt.send(from_pid, ("finished_tokens", None))
    tt.finish(from_pid)
