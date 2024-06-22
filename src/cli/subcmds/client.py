import asyncio
from datetime import datetime
from typing import Annotated, Optional

import rich
from typer import Option, Typer

from src.client.services.by_date import get_log_by_date
from src.client.services.by_ip import get_log_by_ip
from src.db.connection import create_db_connection

subcmd = Typer()


@subcmd.command()
def by_date(
    start: Annotated[Optional[datetime], Option()] = None,
    end: Annotated[Optional[datetime], Option()] = None,
) -> None:
    loop = asyncio.get_event_loop()
    con = create_db_connection()
    loop.run_until_complete(con.connect())
    rich.print([
        log.to_json()
        for log in loop.run_until_complete(get_log_by_date(con, start, end))
    ])


@subcmd.command()
def by_ip(ip: str) -> None:
    loop = asyncio.get_event_loop()
    con = create_db_connection()
    loop.run_until_complete(con.connect())
    rich.print([
        log.to_json()
        for log in loop.run_until_complete(get_log_by_ip(con, ip))
    ])
