from databases import Database

from src.client.dto.log import LogDTO


async def get_log_by_ip(
    connection: Database,
    ip: str,
) -> list[LogDTO]:
    query = "\n".join((
        "SELECT * FROM logs",
        "WHERE ip = :ip"
    ))
    rows = await connection.fetch_all(query, {"ip": ip})
    return [
        LogDTO(
            id=row.id,
            ip=row.ip,
            timestamp=row.timestamp,
            message=row.message,
        )
        for row in rows
    ]
