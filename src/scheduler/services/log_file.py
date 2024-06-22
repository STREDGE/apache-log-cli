import pathlib


def read_logs(log_file: pathlib.Path) -> list[str]:
    return log_file.read_text().strip().split("\n")


def clean_logs(log_file: pathlib.Path) -> None:
    log_file.write_text("")
