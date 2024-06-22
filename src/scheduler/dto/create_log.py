import datetime
from dataclasses import asdict, dataclass


@dataclass
class CreateLogDTO:
    ip: str
    timestamp: datetime.datetime
    message: str

    def to_dict(self) -> dict[str, str | datetime.datetime]:
        return asdict(self)
