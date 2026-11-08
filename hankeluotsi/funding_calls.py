"""Evidence records and conservative local interpretation of public funding calls."""

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from hankeluotsi.funding import TOPICS
from hankeluotsi.schemas import ProjectIdea


CallStatus = Literal["open", "upcoming", "closed", "unknown"]
SNAPSHOT_MAX_AGE = timedelta(hours=6)


class CallDate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    raw: str
    value: date | datetime

    @field_validator("value")
    @classmethod
    def require_aware_time(cls, value):
        if isinstance(value, datetime) and value.utcoffset() is None:
            raise ValueError("Exact times require an explicit UTC offset")
        return value

    @property
    def display(self) -> str:
        suffix = " (date only; exact time/timezone unverified)" if not isinstance(self.value, datetime) else ""
        return self.value.isoformat() + suffix


def parse_call_date(raw: str | None, *, midnight_is_date: bool = False) -> CallDate | None:
    """No timezone is invented for naive times; API midnight placeholders are dates."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            value = date.fromisoformat(raw)
        else:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if value.utcoffset() is None:
                return None
            if midnight_is_date and value.time() == time(0):
                value = value.date()
        return CallDate(raw=raw, value=value)
    except (ValueError, OverflowError):
        return None


class FundingCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    source: Literal["Interreg Aurora", "EU Funding & Tenders Portal"]
    programme: str = Field(min_length=1, max_length=500)
    identifier: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=1000)
    call_identifier: str | None = None
    objectives: str | None = None
    geographic_area: str | None = None
    applicant_requirements: str | None = None
    opening: CallDate | None = None
    deadline: CallDate | None = None
    official_status: CallStatus = "unknown"
    source_url: str
    evidence_url: str
    retrieved_at: AwareDatetime
    source_updated_on: date | None = None
    uncertainties: tuple[str, ...] = ()

    @field_validator("source_url", "evidence_url")
    @classmethod
    def official_https_only(cls, value):
        url = urlsplit(value)
        if (
            url.scheme != "https" or url.hostname not in (
                "www.interregaurora.eu", "ec.europa.eu", "api.tech.ec.europa.eu",
            ) or url.username or url.password or url.port not in (None, 443)
        ):
            raise ValueError("Expected an official HTTPS evidence URL")
        return value


class LiveSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    calls: tuple[FundingCall, ...] = ()
    notices: tuple[str, ...] = ()


def _bounds(value: CallDate) -> tuple[datetime, datetime]:
    if isinstance(value.value, datetime):
        instant = value.value.astimezone(timezone.utc)
        return instant, instant
    midnight = datetime.combine(value.value, time(), tzinfo=timezone.utc)
    # With an unverified timezone, allow the whole UTC-12 to UTC+14 range.
    # An unspecified opening or closing time could be anywhere during that day.
    earliest = midnight - timedelta(hours=14)
    latest = midnight + timedelta(hours=12, days=1)
    return earliest, latest


def assess_call_status(call: FundingCall, *, now: datetime | None = None) -> tuple[CallStatus, str]:
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("Status checks require an aware current time")
    if now - call.retrieved_at > SNAPSHOT_MAX_AGE or call.retrieved_at > now + timedelta(minutes=5):
        return "unknown", "Snapshot is stale or its retrieval time is inconsistent; search again explicitly."
    try:
        opening = _bounds(call.opening) if call.opening else None
        closing = _bounds(call.deadline) if call.deadline else None
    except (ValueError, OverflowError):
        return "unknown", "Published dates are outside the supported calendar range; verify the official source."
    if opening and closing and closing[1] < opening[0]:
        return "unknown", "The published date range is inconsistent."
    if call.official_status == "closed":
        return "closed", "The official source explicitly reports this call closed."
    if closing and now >= closing[1]:
        return "closed", "The published deadline has passed, including date/timezone uncertainty."
    if opening and now < opening[0]:
        if call.official_status == "open":
            return "unknown", "The official open label conflicts with the future opening date."
        return "upcoming", "The published opening date is in the future."
    if call.official_status == "open" and opening and closing and now >= opening[1] and now < closing[0]:
        return "open", "Official open status agrees with the published date window."
    return "unknown", "Missing/conflicting information or a date boundary prevents confirming current status."


def compare_call_locally(idea: ProjectIdea, call: FundingCall) -> tuple[str, ...]:
    project_text = " ".join((idea.title, idea.development_need, *idea.target_groups,
                             idea.expected_change, idea.funding_context or ""))
    source_text = " ".join((call.title, call.objectives or ""))
    project_words = set(re.findall(r"[\w-]+", project_text.casefold()))
    source_words = set(re.findall(r"[\w-]+", source_text.casefold()))
    return tuple(topic for topic, aliases in TOPICS.items()
                 if project_words.intersection(aliases) and source_words.intersection(aliases))
