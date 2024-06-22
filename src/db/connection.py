from databases import Database

from src.core.config import read_toml


def create_db_connection() -> Database:
    return Database(read_toml("db.dsn"))


def create_scheduler_db_connection() -> Database:
    return Database(read_toml("db.scheduler_dsn"))
