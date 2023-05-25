import time
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
        ) strict;
        """,
    ),
)


class Database:
    def __init__(self):
        self.db = None
        self.path = None

    async def init(self):
        log.info("init db...")
        # the db system works by holding two "databases", one lives in
        # :memory:, and when asked to save, dumps all of itself into a
        # separate file
        #
        # when a file is to be opened, then the reverse happens --
        # the file's db is dumped to :memory:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row

        log.info("db initted!")

    async def close(self):
        if self.db:
            await self.db.close()

    @must_be_initialized
    async def run_migrations(self):
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

        log.info("running migrations on db...")
        async with self.db.execute(
            "select max(version) as max from migration_log"
        ) as cursor:
            row = await cursor.fetchone()
        current_version = row["max"] or 0
        log.info("db version: %d", current_version)

        for migration in MIGRATIONS:
            if migration.version > current_version:
                log.info("migrating to version %d", migration.version)

                await self.db.executescript(migration.sql)
                async with self.db.execute_insert(
                    "insert into migration_log (version, applied_at, description) values (?,?,?)",
                    (migration.version, int(time.time()), migration.title),
                ) as _:
                    pass

    @must_be_initialized
    async def open_on(self, path: Path, *, new: bool = False, wipe_memory: bool = True):
        log.info("open %r (new=%r, wipe=%r)", path, new, wipe_memory)
        self.path = path
        existed_before = path.exists()

        if wipe_memory:
            assert new

        async with aiosqlite.connect(self.path) as target_db:
            # either OPEN or NEW will lead to a reset of the entire state
            # SAVE won't

            if wipe_memory:
                await self.close()
                await self.init()

            if not new:
                # opening existing one, reset memory db
                await target_db.backup(self.db)
            else:
                # save structure we already have on target db
                await self.db.backup(target_db)

            await self.run_migrations()

    @must_be_initialized
    async def save(self):
        log.info("saving to %r", self.path)
        async with aiosqlite.connect(self.path) as target_db:
            await self.db.backup(target_db)
