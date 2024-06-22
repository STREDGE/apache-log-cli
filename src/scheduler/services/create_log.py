from databases import Database

from src.scheduler.dto.create_log import CreateLogDTO


async def create_db_log(connection: Database, log: CreateLogDTO) -> None:
    query = "\n".join((
        "INSERT INTO logs (ip, timestamp, message)",
        "VALUES (:ip, :timestamp, :message)"
    ))
    await connection.execute(query, log.to_dict())
