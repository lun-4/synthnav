import asyncio
import json
import random
import logging
import string
import os
import websockets

log = logging.getLogger(__name__)

# Gradio changes this index from time to time. To rediscover it, set VISIBLE = False in
# modules/api.py and use the dev tools to inspect the request made after clicking on the
# button called "Run" at the bottom of the UI
GRADIO_FN = 43


def random_hash():
    letters = string.ascii_lowercase + string.digits
    return "".join(random.choice(letters) for i in range(9))


async def generate_text(input_prompt):
    server = os.environ["SERVER_ADDR"]
    params = {
        "max_new_tokens": 100,
        "do_sample": True,
        "temperature": 0.72,
        "top_p": 0.73,
        "typical_p": 1,
        "repetition_penalty": 1.1,
        "encoder_repetition_penalty": 1.0,
        "top_k": 0,
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
    payload = json.dumps([input_prompt, params])
    session = random_hash()
    url = f"ws://{server}/queue/join"

    log.debug("connecting to %r", url)
    async with websockets.connect(url) as websocket:
        log.debug("connected to %r", url)
        while content := json.loads(await websocket.recv()):
            log.debug("got msg %r", content)
            # Python3.10 syntax, replace with if elif on older
            match content["msg"]:
                case "send_hash":
                    await websocket.send(
                        json.dumps({"session_hash": session, "fn_index": GRADIO_FN})
                    )
                case "estimation":
                    pass
                case "send_data":
                    log.debug("sending data %r", payload)
                    await websocket.send(
                        json.dumps(
                            {
                                "session_hash": session,
                                "event_data": None,
                                "fn_index": GRADIO_FN,
                                "data": [payload],
                            }
                        )
                    )
                case "process_starts":
                    pass
                case "process_generating" | "process_completed":
                    log.debug("got %r", content)
                    yield content["output"]["data"][0]
                    # You can search for your desired end indicator and
                    #  stop generation by closing the websocket here
                    if content["msg"] == "process_completed":
                        log.debug("complete")
                        break

        log.debug("reached end of stream, returning")
