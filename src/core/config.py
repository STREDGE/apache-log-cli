import pathlib
import tomllib
from typing import Any


def read_toml(variable_path: str) -> Any:
    file = pathlib.Path(__file__).parent.parent.parent / "config/config.toml"
    config = tomllib.load(file.open("rb"))
    path = variable_path.split('.')
    return config[path[0]][path[-1]]
