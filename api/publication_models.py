"""Explicit operator contracts for releasing reviewed events to a local map."""

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, StrictStr, field_validator, model_validator

from api.review_models import Contract, DataMode, Note, Operator


Identifier = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9_.:-]{1,160}$")]


class PublicationSelection(Contract):
    event_id: Identifier
    expected_version: Annotated[int, Field(strict=True, ge=1, le=1_000_000_000)]
    location_id: Identifier
    association_checked: Literal[True]
    association_note: Note

    @field_validator("association_checked", mode="before")
    @classmethod
    def explicit_association(cls, value):
        if value is not True:
            raise ValueError("association_checked must be the boolean true")
        return value

    @field_validator("event_id", "location_id")
    @classmethod
    def usable_identifier(cls, value):
        if value != value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("identifier cannot have surrounding whitespace or control characters")
        return value


class PublicationRequest(Contract):
    request_id: Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9_.-]{1,80}$")]
    data_mode: DataMode
    operator: Operator
    note: Note
    period_start: StrictStr
    period_end: StrictStr
    selections: Annotated[list[PublicationSelection], Field(min_length=1, max_length=200)]
    source_conflicts_checked: Literal[True]

    @field_validator("source_conflicts_checked", mode="before")
    @classmethod
    def explicit_source_check(cls, value):
        if value is not True:
            raise ValueError("source_conflicts_checked must be the boolean true")
        return value

    @field_validator("period_start", "period_end")
    @classmethod
    def iso_date(cls, value):
        if len(value) != 10 or date.fromisoformat(value).isoformat() != value:
            raise ValueError("period bounds must be YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def coherent_selection(self):
        if self.period_start > self.period_end:
            raise ValueError("period_start must not exceed period_end")
        identifiers = [selection.event_id for selection in self.selections]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("one canonical event may appear only once")
        self.model_dump_json().encode("utf-8")
        return self
