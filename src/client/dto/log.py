import zoneinfo
from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Address
from uuid import UUID


@dataclass
class LogDTO:
    id: UUID
    ip: IPv4Address
    timestamp: datetime
    message: str

    def to_json(self) -> dict[str, str]:
        return {
            "id": str(self.id),
            "ip": str(self.ip),
            "timestamp": self.timestamp.astimezone(
                zoneinfo.ZoneInfo("Europe/Moscow"),
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "message": self.message,
        }
