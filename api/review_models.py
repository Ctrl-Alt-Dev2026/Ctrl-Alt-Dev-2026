"""Local review contracts; source extraction and operator corrections stay separate."""

from datetime import date
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, StringConstraints, field_validator, model_validator

from ai.router import ArticleInput, ExtractRequest


DataMode = Literal["synthetic", "observed"]
Operator = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Note = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Version = Annotated[int, Field(strict=True, ge=1)]
Status = Literal["pending", "approved", "rejected", "linked"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ImportRequest(ExtractRequest):
    request_id: Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9_.-]{1,80}$")]
    operator: Operator
    data_mode: DataMode

    @model_validator(mode="after")
    def check_mode_and_source(self):
        if (self.article.sursa == "SINTETIC") != (self.data_mode == "synthetic"):
            raise ValueError("data_mode must agree with the explicit SINTETIC source label")
        url = urlsplit(self.article.url)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError("article.url must be an HTTP(S) source URL without credentials")
        if not self.article.article_id.strip() or not self.article.text.strip():
            raise ValueError("article_id and text must not be blank")
        try:
            self.model_dump_json().encode("utf-8")
        except UnicodeError as error:
            raise ValueError("source contains invalid Unicode") from error
        return self


class CandidateFields(Contract):
    data_eveniment: StrictStr | None = None
    ora: Annotated[StrictStr, Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")] | None = None
    loc_text: Annotated[StrictStr, Field(min_length=1, max_length=100_000)] | None = None
    participanti: list[Literal["pieton", "autoturism", "autoutilitara", "biciclist", "motociclist", "autobuz", "camion"]] = Field(default_factory=list)
    cauza_raportata: Literal["viteza", "neacordare_prioritate", "traversare_neregulamentara", "vizibilitate"] | None = None
    gravitate: Literal["deces", "grav", "usor", "necunoscut"] = "necunoscut"
    noapte: StrictBool | None = None
    lat: Annotated[float, Field(strict=True, ge=-90, le=90)] | None = None
    lon: Annotated[float, Field(strict=True, ge=-180, le=180)] | None = None
    precizie_loc: Literal["trecere", "intersectie", "segment", "strada", "vag"] | None = None
    in_iasi: StrictBool | None = None
    location_evidence: Note | None = None

    @field_validator("data_eveniment")
    @classmethod
    def valid_event_date(cls, value):
        if value is not None and (len(value) != 10 or date.fromisoformat(value).isoformat() != value):
            raise ValueError("data_eveniment must be YYYY-MM-DD or null")
        return value

    @field_validator("participanti")
    @classmethod
    def unique_participants(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("participanti must be unique")
        return value

    @model_validator(mode="after")
    def consistent_coordinates(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must both be supplied or both be null")
        if self.lat is not None and self.precizie_loc not in ("trecere", "intersectie", "segment"):
            raise ValueError("a vague/unknown location cannot become a precise map point")
        return self


class CorrectionRequest(Contract):
    data_mode: DataMode
    expected_version: Version
    operator: Operator
    reason: Note
    # Validate the merged document, so a partial patch cannot clear omitted fields.
    changes: Annotated[dict[str, Any], Field(min_length=1)]


class ReviewRequest(Contract):
    data_mode: DataMode
    expected_version: Version
    operator: Operator
    note: Note
    action: Literal["approve", "reject", "link"]
    source_checked: StrictBool = False
    duplicate_checked: StrictBool = False
    location_checked: StrictBool = False
    canonical_event_id: StrictStr | None = None
    expected_event_version: Version | None = None

    @model_validator(mode="after")
    def check_decision(self):
        if self.action in ("approve", "link") and not (self.source_checked and self.duplicate_checked):
            raise ValueError("approval/link requires explicit source and duplicate checks")
        if self.action == "link":
            if not self.canonical_event_id or self.expected_event_version is None:
                raise ValueError("link requires a canonical event and its expected version")
        elif self.canonical_event_id is not None or self.expected_event_version is not None:
            raise ValueError("only link may name an existing canonical event")
        return self


class HistoryEntry(Contract):
    version: Version
    action: Literal["imported", "corrected", "approved", "rejected", "linked"]
    operator: Operator
    at: StrictStr
    note: StrictStr
    changes: dict[str, Any] = Field(default_factory=dict)


class ImportRecord(Contract):
    import_id: StrictStr
    request_id: StrictStr
    request_hash: StrictStr
    data_mode: DataMode
    operator: Operator
    created_at: StrictStr
    article: ArticleInput
    extraction: dict[str, Any]
    candidate_ids: list[str]


class CandidateRecord(Contract):
    candidate_id: StrictStr
    import_id: StrictStr
    article_id: StrictStr
    data_mode: DataMode
    version: Version = 1
    review_status: Status = "pending"
    verificat: StrictBool = False
    canonical_event_id: StrictStr | None = None
    fields: CandidateFields
    original_extraction: dict[str, Any]
    history: list[HistoryEntry]


class ReviewedEvent(Contract):
    event_id: StrictStr
    data_mode: DataMode
    version: Version = 1
    verificat: Literal[True] = True
    publication_status: Literal["not_published"] = "not_published"
    fields: CandidateFields
    candidate_ids: list[str]
    article_ids: list[str]
    urls: list[str]
    source_claims: list[dict[str, Any]]
    history: list[HistoryEntry]


class StoreDocument(Contract):
    schema_version: Literal["review-1"] = "review-1"
    data_mode: DataMode
    imports: dict[str, ImportRecord] = Field(default_factory=dict)
    candidates: dict[str, CandidateRecord] = Field(default_factory=dict)
    events: dict[str, ReviewedEvent] = Field(default_factory=dict)
