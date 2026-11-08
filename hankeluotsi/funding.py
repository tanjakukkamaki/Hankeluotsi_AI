"""Limited official programme research; no call discovery or eligibility decisions.

Only fixed public URLs are fetched. ProjectIdea is accepted by the local comparison
function only, never by the network function. No model or database is used here.
"""

import gzip
import re
import zlib
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from http.client import HTTPException
from io import BytesIO
from typing import Callable, Literal
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict

from hankeluotsi.schemas import ProjectIdea


VERIFIED_ON = date(2026, 11, 8)
TIMEOUT_SECONDS = 5
MAX_PAGE_BYTES = 1_000_000
EURA_URL = "https://eura2021.fi/"
EURA_CALLS_URL = "https://eura2021.fi/hakuilmoitukset/"
AURORA_URL = "https://www.interregaurora.eu/about-us/"
PORTAL_URL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/about"
BUSINESS_FINLAND_URL = "https://www.businessfinland.fi/en/services/funding/"
PUBLIC_PAGE_URLS = (EURA_URL, AURORA_URL, PORTAL_URL, BUSINESS_FINLAND_URL)


class FundingOpportunity(BaseModel):
    """A programme guide is explicitly distinguishable from an individual call."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    record_id: str
    funding_programme: str
    record_kind: Literal["programme_guidance"] = "programme_guidance"
    call_title: str | None = None
    objectives_and_priorities: tuple[str, ...]
    geographic_eligibility: str
    applicant_requirements: str
    application_dates: str | None = None
    status: Literal["open", "closed", "unknown"] = "unknown"
    official_source_url: str
    guidance_urls: tuple[str, ...]
    guidance_verified_on: date = VERIFIED_ON
    information_retrieved_at: datetime | None = None
    retrieved_from_url: str | None = None
    retrieval_state: Literal["not_requested", "retrieved", "unavailable"] = "not_requested"
    source_excerpt: str | None = None
    uncertainty: tuple[str, ...] = (
        "Programme guidance only; no individual call has been retrieved or verified.",
        "Check current call terms, dates, geographical coverage and applicant conditions at the official source.",
    )


def programme_guidance() -> tuple[FundingOpportunity, ...]:
    """Reviewed paraphrases, not a cache of supposedly open opportunities."""
    records = []
    for identifier, name, objectives, geography, evidence in (
        (
            "eakr", "EURA 2021 — EAKR / ERDF",
            ("Regional development, innovation, SMEs, digitalisation and green transition.",),
            "Finnish regional or national calls; check the territory of the specific call.",
            "european-regional-development-fund-erdf_en",
        ),
        (
            "esr", "EURA 2021 — ESR+ / ESF+",
            ("Employment, education, skills and social inclusion.",),
            "Finnish regional or national calls; check the territory of the specific call.",
            "european-social-fund_en",
        ),
        (
            "jtf", "EURA 2021 — JTF",
            ("Economic diversification and workforce transition towards climate neutrality, including reskilling.",),
            "Designated just-transition territories; Finnish coverage must be checked in the call.",
            "just-transition-fund_en",
        ),
    ):
        records.append(FundingOpportunity(
            record_id=identifier, funding_programme=name,
            objectives_and_priorities=objectives, geographic_eligibility=geography,
            applicant_requirements="Unknown for individual calls; consult the funding authority's EURA notice.",
            official_source_url=EURA_CALLS_URL,
            guidance_urls=(
                "https://commission.europa.eu/funding-and-tenders/find-funding/eu-funding-programmes/" + evidence,
                EURA_URL,
            ),
        ))
    records.extend((
        FundingOpportunity(
            record_id="aurora", funding_programme="Interreg Aurora",
            objectives_and_priorities=(
                "Innovation and SME competitiveness; green transition; education, culture and sustainable tourism; cross-border capacity.",
            ),
            geographic_eligibility="Specified northern regions of Finland, Sweden and Norway, and Sápmi; not entire countries.",
            applicant_requirements="Check partner types, cross-border partnership conditions, exceptions and call-specific terms in the programme manual.",
            official_source_url="https://www.interregaurora.eu/projects/calls-for-applications-2/",
            guidance_urls=(
                "https://www.interregaurora.eu/about-us/programme-specific-objectives/",
                "https://www.interregaurora.eu/programme-manual/apply-for-a-project/programme-area/",
                "https://www.interregaurora.eu/programme-manual/apply-for-a-project/eligible-partners/",
            ),
        ),
        FundingOpportunity(
            record_id="portal", funding_programme="EU Funding & Tenders Portal — multiple programmes",
            objectives_and_priorities=("Discovery of EU funding across multiple programmes; priorities depend on the specific programme and call.",),
            geographic_eligibility="Unknown until an individual programme and call are selected.",
            applicant_requirements="Unknown until an individual call is selected; consult its conditions and reference documents.",
            official_source_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals",
            guidance_urls=(PORTAL_URL,),
        ),
        FundingOpportunity(
            record_id="business_finland", funding_programme="Business Finland — Finnish public funding",
            objectives_and_priorities=("Innovation, research and product development, business renewal and international growth.",),
            geographic_eligibility="Finnish funding context; instrument-specific territorial requirements must be checked.",
            applicant_requirements="Services include companies and research organisations; each instrument has its own applicant requirements.",
            official_source_url=BUSINESS_FINLAND_URL,
            guidance_urls=(BUSINESS_FINLAND_URL,),
            uncertainty=(
                "Programme guidance only; no individual call has been retrieved or verified.",
                "Business Finland instruments are not necessarily EU-funded. Check the individual instrument's conditions.",
            ),
        ),
    ))
    return tuple(records)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Source redirected; open its official link manually.")


class _PageSummary(HTMLParser):
    """Read only page title and description; never interpret these as call terms."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.title_parts = []
        self.description = ""

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "meta" and (
            (values.get("name") or "").lower() == "description"
            or (values.get("property") or "").lower() == "og:description"
        ):
            self.description = values.get("content") or ""

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)


def _fetch_public_page(url: str) -> str:
    if url not in PUBLIC_PAGE_URLS:
        raise ValueError("Only the fixed official programme pages may be retrieved.")
    request = Request(url, headers={
        "User-Agent": "HankeLuotsiAI/0.1 (public programme research)",
        "Accept": "text/html",
    })
    # Default certificate validation stays enabled. Redirects are not followed.
    with build_opener(_NoRedirect()).open(request, timeout=TIMEOUT_SECONDS) as response:
        if response.headers.get_content_type() != "text/html":
            raise ValueError("Source did not return an HTML programme page.")
        content = response.read(MAX_PAGE_BYTES + 1)
        if len(content) > MAX_PAGE_BYTES:
            raise ValueError("Source page exceeds the retrieval size limit.")
        encoding = response.headers.get("Content-Encoding", "identity").lower()
        if encoding == "gzip":
            try:
                with gzip.GzipFile(fileobj=BytesIO(content)) as compressed:
                    content = compressed.read(MAX_PAGE_BYTES + 1)
            except (EOFError, zlib.error) as error:
                raise ValueError("Source returned an invalid compressed page.") from error
            if len(content) > MAX_PAGE_BYTES:
                raise ValueError("Decoded source page exceeds the retrieval size limit.")
        elif encoding not in ("", "identity"):
            raise ValueError("Source uses an unsupported content encoding.")
        try:
            return content.decode(response.headers.get_content_charset() or "utf-8")
        except (UnicodeError, LookupError) as error:
            raise ValueError("Source page could not be decoded using its declared text encoding.") from error


def retrieve_funding_opportunities(
    *, retrieve_live: bool = False, fetch_page: Callable[[str], str] | None = None,
) -> tuple[FundingOpportunity, ...]:
    """Return six guides, optionally with live page metadata from four fixed URLs.

    Intentionally takes no project, keywords or user text. Failures are isolated by
    source and leave the verified guidance available. No hidden network retries.
    """
    guides = programme_guidance()
    if not retrieve_live:
        return guides
    fetch = fetch_page or _fetch_public_page
    outcomes = {}
    for url in PUBLIC_PAGE_URLS:
        try:
            parser = _PageSummary()
            parser.feed(fetch(url))
            title = " ".join(" ".join(parser.title_parts).split())
            description = " ".join(parser.description.split())
            # A title-only JavaScript shell provides no usable programme detail.
            if not title or len(description) < 40:
                raise ValueError("No usable programme description; the page may require JavaScript.")
            outcomes[url] = (f"{title[:160]} — {description[:600]}", None, datetime.now(timezone.utc))
        except (URLError, OSError, HTTPException, ValueError, LookupError) as error:
            reason = (
                "Network, certificate or HTTP access failed; open the official source manually."
                if isinstance(error, (URLError, OSError, HTTPException)) else str(error)
            )
            outcomes[url] = (None, reason, None)
    source_for_record = {
        "eakr": EURA_URL, "esr": EURA_URL, "jtf": EURA_URL,
        "aurora": AURORA_URL, "portal": PORTAL_URL, "business_finland": BUSINESS_FINLAND_URL,
    }
    records = []
    for guide in guides:
        excerpt, error, retrieved_at = outcomes[source_for_record[guide.record_id]]
        records.append(guide.model_copy(update={
            "source_excerpt": excerpt,
            "information_retrieved_at": retrieved_at,
            "retrieved_from_url": source_for_record[guide.record_id] if retrieved_at else None,
            "retrieval_state": "unavailable" if error else "retrieved",
            "uncertainty": guide.uncertainty + ((error,) if error else ()),
        }))
    return tuple(records)


# Transparent bilingual topic vocabulary; no semantic model, score or eligibility
# classification. An overlap is a prompt for manual research, never a verdict.
TOPICS = {
    "innovation": ("innovation", "innovations", "innovaatio", "innovaatiot"),
    "digital": ("digital", "digitalisation", "digitalization", "digitaalinen", "digitaaliset", "digitalisaatio"),
    "skills": ("skills", "education", "training", "reskilling", "osaaminen", "osaamisen", "koulutus"),
    "employment": ("employment", "työllisyys", "työllisyyden"),
    "inclusion": ("inclusion", "osallisuus", "osallisuuden"),
    "green transition": ("green", "climate", "sustainable", "vihreä", "ilmasto", "kestävä"),
    "culture": ("culture", "cultural", "kulttuuri", "kulttuurin"),
    "tourism": ("tourism", "matkailu", "matkailun"),
    "research": ("research", "tutkimus", "tutkimuksen"),
    "SMEs": ("sme", "smes", "pk", "pk-yritys", "pk-yritykset"),
    "international growth": ("international", "kansainvälinen", "kansainvälistyminen"),
    "cross-border": ("cross-border", "crossborder", "rajat", "rajatylittävä"),
}


def compare_locally(idea: ProjectIdea, opportunity: FundingOpportunity) -> tuple[str, ...]:
    """Return shared vocabulary topics; geography/applicant eligibility is not inferred."""
    project_text = " ".join((
        idea.title, idea.development_need, *idea.target_groups,
        idea.expected_change, idea.funding_context or "",
    ))
    programme_text = " ".join(opportunity.objectives_and_priorities)
    project_words = set(re.findall(r"[\w-]+", project_text.casefold()))
    programme_words = set(re.findall(r"[\w-]+", programme_text.casefold()))
    return tuple(
        topic for topic, vocabulary in TOPICS.items()
        if project_words.intersection(vocabulary) and programme_words.intersection(vocabulary)
    )
