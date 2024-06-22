from datetime import datetime

from databases import Database

from src.client.dto.log import LogDTO


async def get_log_by_date(
    connection: Database,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[LogDTO]:
    if not any((start, end)):
        raise ValueError("Диапазон не может быть пустым")
    params = {}
    query = "\n".join((
        "SELECT * FROM logs",
        "WHERE "
    ))
    if not start and end:
        params |= {"end": end}
        query += "timestamp <= :end"
    if not end and start:
        params |= {"start": start}
        query += "timestamp >= :start"
    if start and end:
        params |= {"start": start, "end": end}
        query += "timestamp >= :start and timestamp <= :end"
    rows = await connection.fetch_all(query, params)
    return [
        LogDTO(
            id=row.id,
            ip=row.ip,
            timestamp=row.timestamp,
            message=row.message,
        )
        for row in rows
    ]
