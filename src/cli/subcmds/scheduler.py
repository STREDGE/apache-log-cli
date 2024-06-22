import asyncio

import rich
from typer import Typer

from src.scheduler.run import start_scheduler

subcmd = Typer()


@subcmd.command()
def start() -> None:
    rich.print("Запустил сбор логов.")
    asyncio.run(start_scheduler())
