import asyncio

from src.scheduler.broker import create_broker
from src.scheduler.task import read_logs_and_save


async def start_scheduler() -> None:
    broker = create_broker()
    task = broker.register_task(read_logs_and_save)

    await broker.startup()
    while True:
        await task.kiq()
        await asyncio.sleep(5)
