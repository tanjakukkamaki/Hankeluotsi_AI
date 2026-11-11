"""Deterministic research relevance, separate from immutable facts and eligibility.

No network, model calls, persistence or application decisions. Rule version 1.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

from hankeluotsi.funding_calls import FundingCall, assess_call_status
from hankeluotsi.funding_eu import MAX_PAGES, _page_url
from hankeluotsi.live_funding import AURORA_CALLS_URL, _valid_csv_url
from hankeluotsi.schemas import ConceptPaper, ProjectIdea


RELEVANCE_CATEGORIES = ("High", "Medium", "Low", "Insufficient Information")
# Specific themes carry more weight than broad words such as research/digital.
THEMES = {
    "culture & creative work": (5, ("art", "arts", "artists", "culture", "cultural", "creative industries", "creative industry", "taide", "taiteen", "kulttuuri", "kulttuurin", "luovat alat")),
    "skills & learning": (5, ("skills", "learning", "education", "training", "reskilling", "osaaminen", "osaamisen", "koulutus", "digitaidot", "digitaitoja")),
    "community development": (5, ("community", "communities", "neighbourhood", "neighborhood", "civic", "yhteisö", "yhteisöjen", "yhteisöllisyys", "kylä")),
    "inclusion": (4, ("inclusion", "inclusive", "accessibility", "osallisuus", "osallisuuden", "saavutettavuus")),
    "employment": (4, ("employment", "unemployment", "työllisyys", "työllisyyden")),
    "tourism": (4, ("tourism", "tourist", "matkailu", "matkailun")),
    "climate & environment": (4, ("climate", "environment", "biodiversity", "solar radiation", "nature restoration", "ecosystem", "ilmasto", "ympäristö", "luonnon monimuotoisuus")),
    "energy": (4, ("energy", "electricity", "renewable", "geothermal", "sedimentary", "hydrocarbon", "energia", "energian")),
    "health": (4, ("health", "healthcare", "medical", "terveys", "terveyden")),
    "manufacturing": (4, ("manufacturing", "factory", "industrial production", "valmistus", "teollisuus")),
    "agriculture": (4, ("agriculture", "farming", "maatalous", "maatalouden")),
    "digital": (1, ("digital", "digitalisation", "digitalization", "digitaalinen", "digitaaliset", "digitalisaatio", "digitaidot", "digitaitoja")),
    "research": (1, ("research", "tutkimus", "tutkimuksen")),
    "innovation": (1, ("innovation", "innovations", "innovaatio", "innovaatiot")),
}
BROAD_THEMES = {"digital", "research", "innovation"}
COUNTRIES = {
    "Finland": ("finland", "finnish", "suomi", "suomessa", "suomen"),
    "Sweden": ("sweden", "swedish", "sverige", "ruotsi", "ruotsin"),
    "Norway": ("norway", "norwegian", "norge", "norja", "norjan"),
    "Denmark": ("denmark", "danish", "tanska"),
    "Estonia": ("estonia", "estonian", "viro"),
    "Germany": ("germany", "german", "saksa"),
}
REGIONS = {
    "Lapland": ("lapland", "lappi", "lapin"),
    "North Ostrobothnia": ("north ostrobothnia", "pohjois-pohjanmaa", "pohjois-pohjanmaan"),
    "Norrbotten": ("norrbotten",), "Västerbotten": ("västerbotten",),
    "Troms": ("troms",), "Finnmark": ("finnmark",),
}
ORGANISATIONS = {
    "non-profit/NGO": ("ngo", "ngos", "non-profit", "nonprofit", "association", "associations", "yhdistys", "yhdistykset"),
    "university": ("university", "universities", "yliopisto", "ammattikorkeakoulu"),
    "SME": ("sme", "smes", "pk-yritys", "pk-yritykset"),
    "public authority": ("public authority", "public authorities", "municipality", "municipalities", "kunta", "kunnat"),
}


def _mentions(text: str, aliases: tuple[str, ...]) -> bool:
    """Whole words/phrases only; reject nearby explicit thematic negation."""
    text = text.casefold()
    for alias in aliases:
        for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text):
            before = text[max(0, match.start() - 35):match.start()]
            if not re.search(r"\b(?:not|no|without|excluding|ei)\b(?:\W+\w+){0,3}\W*$", before):
                return True
    return False


def _labels(text: str, vocabulary: dict) -> set[str]:
    return {label for label, aliases in vocabulary.items() if _mentions(text, aliases)}


def _theme_mentions(text: str, theme: str, aliases: tuple[str, ...]) -> bool:
    if theme == "culture & creative work":
        # These scientific/business phrases are not evidence of arts/cultural work.
        text = re.sub(r"\bstate[\s-]+of[\s-]+the[\s-]+art\b", " ", text, flags=re.IGNORECASE)
        modifiers = "innovation|research|safety|security|business|entrepreneurial|organisational|organizational|cell|bacterial|microbial|tissue"
        text = re.sub(r"\b(?:" + modifiers + r")\s+cultures?\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\bcultures?\s+(?:of|within|in)\s+(?:" + modifiers + r")\b", " ", text, flags=re.IGNORECASE)
    return _mentions(text, aliases)


def source_reference_confirmed(call: FundingCall) -> bool:
    """Check the existing adapter contracts, not current remote availability.

    Successful retrieval is established by the adapters. A domain alone is not
    enough: the topic identifier and evidence endpoint must also agree.
    """
    if call.source == "Interreg Aurora":
        return call.source_url == AURORA_CALLS_URL and _valid_csv_url(call.evidence_url)
    url = urlsplit(call.source_url)
    expected = "/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/" + call.identifier
    return bool(
        re.fullmatch(r"HORIZON-[A-Za-z0-9-]+", call.identifier, re.IGNORECASE)
        and url.scheme == "https" and url.hostname == "ec.europa.eu"
        and not url.username and not url.password and url.port in (None, 443)
        and unquote(url.path).rstrip("/").casefold() == expected.casefold()
        and not url.query and not url.fragment
        and call.evidence_url in {_page_url(page) for page in range(1, MAX_PAGES + 1)}
    )


@dataclass(frozen=True)
class FundingMatch:
    call: FundingCall
    category: str
    score: int | None
    thematic_points: int
    geography_points: int
    applicant_points: int
    confidence: str
    matched_topics: tuple[str, ...]
    reasons: tuple[str, ...]
    cautions: tuple[str, ...]
    source_reference_confirmed: bool
    status: str
    status_reason: str


def _context_points(project_text: str, source_text: str | None, vocabulary: dict, label: str):
    if not source_text:
        return 0, f"{label}: official information is missing; no compatibility assumed.", False
    if re.search(r"\b(?:not|except|excluding|outside|ei)\b", source_text.casefold()):
        return 0, f"{label}: source text contains exclusions; check the full conditions manually.", False
    project_labels, source_labels = _labels(project_text, vocabulary), _labels(source_text, vocabulary)
    shared = sorted(project_labels & source_labels)
    if shared:
        return 10, f"{label} wording overlaps: {', '.join(shared)}. This does not confirm eligibility.", False
    if project_labels and source_labels:
        return -5, f"{label}: named categories differ; manual checking is required, not an exclusion decision.", True
    return 0, f"{label}: insufficient recognised wording for comparison; no compatibility assumed.", False


def match_funding_call(idea: ProjectIdea, call: FundingCall, *, concept: ConceptPaper | None = None,
                       now: datetime | None = None) -> FundingMatch:
    now = now or datetime.now(timezone.utc)
    status, status_reason = assess_call_status(call, now=now)
    reference_ok = source_reference_confirmed(call)
    objectives = tuple(objective.description for objective in concept.objectives) if concept else ()
    primary = " ".join((idea.title, idea.development_need, idea.expected_change, *objectives))
    groups = " ".join(idea.target_groups)
    weights, matches = {}, []
    earned = 0.0
    for theme, (weight, aliases) in THEMES.items():
        in_primary = _theme_mentions(primary, theme, aliases)
        if not in_primary and not _theme_mentions(groups, theme, aliases):
            continue
        weights[theme] = weight * (2 if in_primary else 1)
        strength = 1 if _theme_mentions(call.title, theme, aliases) else 0.8 if _theme_mentions(call.objectives or "", theme, aliases) else 0
        if strength:
            earned += weights[theme] * strength
            matches.append(theme)
    thematic = round(80 * earned / sum(weights.values())) if weights else 0
    reasons = ["Thematic overlap in title/objectives: " + (", ".join(matches) or "none detected by these rules") + "."]
    cautions = []
    if matches and not set(matches) - BROAD_THEMES:
        thematic = min(thematic, 24)
        cautions.append("Only broad digital/research/innovation wording overlaps; theme points are capped at 24 (Low).")
    title_themes = {theme for theme, (_, aliases) in THEMES.items()
                    if theme not in BROAD_THEMES and _theme_mentions(call.title, theme, aliases)}
    unsupported_focus = title_themes - weights.keys()
    if unsupported_focus:
        cautions.append("Call title focuses on " + ", ".join(sorted(unsupported_focus))
                        + ", absent from the project's recognised themes. Incidental overlaps need careful checking.")
        if not title_themes.intersection(matches):
            thematic = min(thematic, 24)
            cautions.append("No specific shared theme in this specialist title; theme points are capped at 24 (Low).")
    geo, geo_reason, geo_difference = _context_points(idea.geography, call.geographic_area, COUNTRIES, "Geography")
    region, region_reason, region_difference = _context_points(idea.geography, call.geographic_area, REGIONS, "Named region")
    if region > 0 or region_difference:
        geo, geo_reason = region, region_reason
    elif geo > 0:
        geo = 5  # A country overlap does not establish membership of a programme subregion.
    reasons.append(geo_reason)
    if idea.partners:
        applicant, applicant_reason, applicant_difference = _context_points(" ".join(idea.partners), call.applicant_requirements, ORGANISATIONS, "Partner type")
    else:
        applicant, applicant_difference = 0, False
        applicant_reason = "Applicant organisation type is unspecified; target groups are not treated as applicants."
    reasons.append(applicant_reason)
    if not call.applicant_requirements:
        cautions.append("Official applicant requirements are missing; no applicant compatibility assumed.")
    cautions.append("Applicant/legal status, partnerships and full geographical conditions still require human verification.")
    description_present = bool(call.objectives and len(call.objectives.strip()) >= 40)
    specific = set(matches) - BROAD_THEMES
    if not weights or (not description_present and not specific) or not reference_ok:
        category = "Insufficient Information"
    elif thematic >= 55 and len(specific) >= 2:
        category = "High"
    elif thematic >= 25 and specific:
        category = "Medium"
    else:
        category = "Low"
    if category == "High" and (not description_present or geo_difference or region_difference or applicant_difference):
        category = "Medium"
    if not description_present:
        cautions.append("A substantive objectives/description excerpt is missing; title-only clues cannot receive High relevance.")
    if not reference_ok:
        cautions.append("Official source reference could not be confirmed against a supported adapter. This record is not verified or scored.")
        status, status_reason = "unknown", "Official source reference is unconfirmed; published facts require checking."
    if not weights:
        cautions.append("No project themes were recognised by the small English/Finnish vocabulary.")
    if status == "unknown":
        cautions.append("Current call status is unknown: " + status_reason)
    confidence = "Moderate" if description_present and reference_ok and status != "unknown" and category != "Insufficient Information" else "Limited"
    if confidence == "Moderate" and geo > 0 and applicant > 0 and len(specific) >= 2:
        confidence = "Stronger"
    score = None if category == "Insufficient Information" else max(0, min(100, thematic + geo + applicant))
    return FundingMatch(call, category, score, thematic, geo, applicant, confidence,
                        tuple(matches), tuple(reasons), tuple(cautions), reference_ok, status, status_reason)


def rank_funding_calls(idea: ProjectIdea, calls: tuple[FundingCall, ...], *,
                       concept: ConceptPaper | None = None, now: datetime | None = None) -> tuple[FundingMatch, ...]:
    now = now or datetime.now(timezone.utc)
    matches = [match_funding_call(idea, call, concept=concept, now=now) for call in calls]
    status_order = {"open": 0, "upcoming": 1, "closed": 2, "unknown": 3}
    return tuple(sorted(matches, key=lambda item: (RELEVANCE_CATEGORIES.index(item.category),
        -(item.score if item.score is not None else -1), status_order[item.status], item.call.source, item.call.identifier)))
