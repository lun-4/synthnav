# synthnav

attempting to be a better (for me) LLM-powered story writing tool

![like this](https://smooch.computer/i/xn97dftt.png)

status: prototype

## installation

- [text-generation-webui](https://github.com/oobabooga/text-generation-webui)
  - must run with `--notebook` mode so that API becomes available
- get python3

```
git clone ...
cd ...
python3 -m venv env
env/bin/pip install -Ur requirements.txt
env SERVER_ADDR=1.1.1.1:1234 env/bin/python3 ./start.py
```
