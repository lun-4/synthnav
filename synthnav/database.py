import logging
import aiosqlite
from pathlib import Path
from dataclasses import dataclass

log = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.db = None

    async def create_on(self, path):
        log.info("create %r", path)

    async def open_on(self, path):
        log.info("open %r", path)
