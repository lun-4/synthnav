import logging
import aiosqlite
from pathlib import Path
from dataclasses import dataclass

log = logging.getLogger(__name__)


def must_be_initialized(function):
    def wrapped(self, *args, **kwargs):
        assert self.db is not None
        return function(self, *args, **kwargs)

    return wrapped


@dataclass
class Migration:
    version: int
    title: str
    sql: str


MIGRATIONS = (
    Migration(
        1,
        "initial db schema",
        """
        create table generations (
            id text primary key,
            state int not null,
            data text not null
        ) strict;

        create table generation_parents (
            parent_id text not null
                constraint parent_fk references generations (id) on delete restrict,
            child_id text not null
                constraint child_fk references generations (id) on delete restrict,
            constraint parent_child_pk primary key (parent_id, child_id)
        """,
    ),
)


class Database:
    def __init__(self):
        self.db = None
        self.path = None

    async def init(self):
        # the db system works by holding two "databases", one lives in
        # :memory:, and when asked to save, dumps all of itself into a
        # separate file
        #
        # when a file is to be opened, then the reverse happens --
        # the file's db is dumped to :memory:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row

        # all databases must have migration_log
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS migration_log (
                version INT PRIMARY KEY,
                applied_at INT,
                description TEXT
            ) STRICT;
            """
        )

    async def close(self):
        if self.db:
            await self.db.close()

    @must_be_initialized
    async def run_migrations(self):
        log.info("running migrations on db...")
        async with self.db.execute("select max(version) from migration_logs") as cursor:
            row = await cursor.fetchone()
        current_version = row["max"] or 0
        log.info("db version: %d", current_version)

        for migration in MIGRATIONS:
            if migration.version > current_version:
                log.info("migrating to version %d", migration.version)
                await self.db.execute(migration.sql)
                await self.db.execute(
                    "insert into migration_logs (version, applied_at, description) values (?,?,?)",
                    (migration.version, int(time.time()), migration.title),
                )

    @must_be_initialized
    async def open_on(self, path: Path):
        log.info("open %r", path)
        self.path = path

        async with aiosqlite.connect(self.path) as target_db:
            await self.close()
            await self.init()
            await target_db.backup(self.db)
            await self.run_migrations()

    @must_be_initialized
    async def save(self):
        log.info("saving to %r", self.path)
        async with aiosqlite.connect(self.path) as target_db:
            await self.db.backup(target_db)
