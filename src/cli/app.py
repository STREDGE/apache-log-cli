from typer import Typer

from src.cli.subcmds import client, scheduler


def init_cli() -> None:
    app = Typer(pretty_exceptions_short=False, pretty_exceptions_enable=False)
    app.add_typer(scheduler.subcmd, name="scheduler")
    app.add_typer(client.subcmd, name="get_log")
    app()
