import time
import logging
import aiosqlite
from pathlib import Path
from .tinytask import producer
from dataclasses import dataclass
from uuid import UUID
from .generation import GenerationState, Generation

log = logging.getLogger(__name__)


def must_be_initialized(function):
    def wrapped(self, *args, **kwargs):
        assert self.db is not None
        return function(self, *args, **kwargs)

    return wrapped


def change(function):
    """Signal that a function changes the database."""
    function.__changes_db = True
    return must_be_initialized(function)


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
        assert self.db is None  # do not call init() on already-initted db

        log.info("initializing memory db...")
        # the db system works by holding two "databases", one lives in
        # :memory:, and when asked to save, dumps all of itself into a
        # separate file
        #
        # when a file is to be opened, then the reverse happens --
        # the file's db is dumped to :memory:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row

        log.info("memory db running!")
        await self.run_migrations()

    async def close(self):
        if self.db:
            log.info("closing db")
            await self.db.close()
            self.db = None
            log.info("db closed")

    @must_be_initialized
    async def run_migrations(self):
        log.info("running migrations on db...")
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
                await self.db.execute_insert(
                    "insert into migration_log (version, applied_at, description) values (?,?,?)",
                    (migration.version, int(time.time()), migration.title),
                )

    @must_be_initialized
    async def open_on(self, path: Path, *, new: bool = False, wipe_memory: bool = True):
        log.info("open %r (new=%r, wipe=%r)", path, new, wipe_memory)
        self.path = path
        existed_before = path.exists()

        async with aiosqlite.connect(self.path) as target_db:
            # either OPEN or NEW will lead to a reset of the entire state
            # SAVE won't

            if wipe_memory:
                await self.close()
                await self.init()

            await self.db.commit()
            await target_db.commit()

            if not new:
                # opening existing one, reset memory db
                await target_db.backup(self.db)
            else:
                # save structure we already have on target db
                await self.db.backup(target_db)

            log.debug("running migrations...")
            await self.run_migrations()

        log.info("done")

    @must_be_initialized
    async def save(self):
        log.info("saving to %r", self.path)
        async with aiosqlite.connect(self.path) as target_db:
            await self.db.commit()
            await target_db.commit()
            await self.db.backup(target_db)
        log.info("done")

    @producer
    @must_be_initialized
    async def fetch_all_generations(self, tt, from_pid):
        async with self.db.execute("select id, state, data from generations") as cursor:
            async for row in cursor:
                generation = Generation(
                    id=UUID(row["id"]),
                    state=GenerationState(row["state"]),
                    text=row["data"],
                    parent=None,  # TODO use a join to find parent
                )
                tt.send(from_pid, ("generation", generation))

        async with self.db.execute(
            "select parent_id, child_id from generation_parents"
        ) as cursor:
            async for row in cursor:
                tt.send(from_pid, ("parent", row["parent_id"], row["child_id"]))

        tt.send(from_pid, ("done",))
        tt.finish(from_pid)

    @change
    async def update_generation(self, generation):
        await self.db.execute_insert(
            "update generations set state = ?, data = ? where id = ?",
            (
                generation.state,
                generation.text,
                str(generation.id),
            ),
        )

    @change
    async def insert_generation(self, generation):
        await self.db.execute_insert(
            "insert into generations (id,state,data) values (?,?,?)",
            (str(generation.id), generation.state.value, generation.text),
        )
        if generation.parent:
            await self.db.execute_insert(
                "insert into generation_parents (parent_id,child_id) values (?,?)",
                (str(generation.parent), str(generation.id)),
            )
