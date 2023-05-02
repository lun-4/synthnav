import asyncio
import json
import random
import logging
import string
import os
import websockets
from typing import Generator

log = logging.getLogger(__name__)

GENERATION_LOCK = asyncio.Lock()


async def generate_text(input_prompt: str, *, seed=-1) -> Generator[str, None, None]:
    """From a givenv input prompt, spit out the tokens that compose the
    textual completion of that prompt."""

    server = os.environ["SERVER_ADDR"]
    request = {
        "prompt": input_prompt,
        "max_new_tokens": 100,
        "do_sample": True,
        "temperature": 0.75,
        "top_p": 0.73,
        "typical_p": 1,
        "repetition_penalty": 1.18,
        "top_k": 40,
        "min_length": 0,
        "no_repeat_ngram_size": 0,
        "num_beams": 1,
        "penalty_alpha": 0,
        "length_penalty": 1,
        "early_stopping": False,
        "seed": seed,
        "add_bos_token": True,
        "truncation_length": 2048,
        "ban_eos_token": False,
        "skip_special_tokens": True,
        "stopping_strings": [],
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
