# synthnav

attempting to be a better (for me) LLM-powered story writing tool

![like this](https://smooch.computer/i/unitj6hn.png)

![the idea pad i made in obsidian to explain it](https://smooch.computer/i/wkshy6vy.png)

quick status: its a prototype

status: you can write a story and somewhat ship it. bugs beware. no persistence

## installation

- [text-generation-webui](https://github.com/oobabooga/text-generation-webui)
  - tested with commit ee68ec9079492a72a35c33d5000da432ce94af71
  - must run with `--api` for this to be able to generate any text
- get python3

```
git clone ...
cd ...
python3 -m venv env
env/bin/pip install -Ur requirements.txt
env SERVER_ADDR=localhost:5005 env/bin/python3 ./start.py
```
