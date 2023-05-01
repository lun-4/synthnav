import asyncio
import json
import random
import logging
import string
import os
import websockets

log = logging.getLogger(__name__)

GENERATION_LOCK = asyncio.Lock()


async def generate_text(input_prompt):
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
        "seed": -1,
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
                        result = result + content
                        log.debug("got %r: %r", content, result)
                        yield result
                    case "stream_end":
                        return

    log.debug("reached end of stream, returning")
