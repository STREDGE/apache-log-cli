import pathlib
import re
import zoneinfo
from datetime import datetime

from src.core.config import read_toml
from src.db.connection import create_scheduler_db_connection
from src.scheduler.dto.create_log import CreateLogDTO
from src.scheduler.services.create_log import create_db_log
from src.scheduler.services.log_file import clean_logs, read_logs


async def read_logs_and_save() -> None:
    file = pathlib.Path(read_toml("files.log"))
    logs = read_logs(file)

    db = create_scheduler_db_connection()
    await db.connect()
    for log in logs:
        if not log:
            continue
        await create_db_log(
            db,
            CreateLogDTO(
                ip=log.split()[0],
                timestamp=datetime.fromtimestamp(
                    float(log.split()[3]),
                    zoneinfo.ZoneInfo("Europe/Moscow"),
                ),
                message=re.search(r'".*"', log).group().replace('"', ""),
            ),
        )
    clean_logs(file)
    await db.disconnect()
