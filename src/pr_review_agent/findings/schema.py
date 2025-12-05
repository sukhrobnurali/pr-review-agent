from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AgentName = Literal["security", "performance", "tests", "quality"]


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank >= other.rank


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class FileLocation(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str = Field(..., min_length=1)
    line: int = Field(..., ge=1)
    end_line: int | None = Field(default=None, ge=1)

    @field_validator("end_line")
    @classmethod
    def end_line_after_line(cls, v: int | None, info: object) -> int | None:
        if v is None:
            return v
        data = getattr(info, "data", {})
        line = data.get("line")
        if line is not None and v < line:
            raise ValueError("end_line must be >= line")
        return v


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: Severity
    location: FileLocation
    agent: AgentName
    title: str = Field(..., min_length=1, max_length=200)
    explanation: str = Field(..., min_length=1)
    suggestion: str | None = None
