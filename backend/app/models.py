from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_TICK = 2**53 - 1


class Event(BaseModel):
    time: int
    value: str


class Signal(BaseModel):
    id: str
    name: str
    scope: str
    width: int
    kind: str
    events: list[Event]


class Source(BaseModel):
    name: str
    content: str


class Trace(BaseModel):
    id: str
    name: str
    timescale: str
    tick_fs: int
    start: int
    end: int
    signals: list[Signal]
    sources: list[Source] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    time: int = Field(ge=0, le=MAX_TICK)
    signals: list[str] = Field(min_length=1, max_length=16)
    window: int = Field(default=20000, ge=0, le=MAX_TICK)
    clock: str | None = None
    edge: Literal["rising", "falling"] = "rising"
    reset: str | None = None
    reset_active: Literal["0", "1"] = "1"
    reset_mode: Literal["unknown", "synchronous", "asynchronous"] = "unknown"


class ExplainRequest(AnalysisRequest):
    question: str = Field(min_length=1, max_length=2000)
    consent: bool = False
    include_rtl: bool = False


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str = Field(min_length=1, max_length=4000)
    observed_facts: list[str] = Field(max_length=64)
    possible_explanations: list[str] = Field(max_length=32)
    related_signals: list[str] = Field(max_length=16)
    related_code: list[str] = Field(max_length=32)
    suggested_checks: list[str] = Field(max_length=32)
    limitations: list[str] = Field(max_length=32)
