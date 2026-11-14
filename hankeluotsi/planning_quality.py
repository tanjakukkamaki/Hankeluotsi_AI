"""Context-limited advisories, separate from persisted approval-gating checks."""

from collections import Counter
from datetime import date
import re
import unicodedata

from hankeluotsi.consistency import FindingSeverity
from hankeluotsi.draft_checks import DraftFinding


VERSION = "planning_advisories_v1"
LABEL = re.compile(r"^(?:partner|kumppani)\s*:\s*", re.IGNORECASE)
ISO_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
YEAR = re.compile(r"(?<!\d)(?:19|20|21)\d{2}(?!\d)")


def check_planning_advisories(draft, *, reference_date):
    if type(reference_date) is not date:
        raise ValueError("An explicit planning reference date is required")
    observations, names = [], []
    for partner in draft.partner_roles:
        name = unicodedata.normalize("NFKC", partner.partner).strip()
        if LABEL.match(name):
            observations.append(DraftFinding("PARTNER_NAME_HAS_LABEL", FindingSeverity.WARNING,
                "A partner name includes a field label. Verify it and use only the organisation name.", "partner_roles"))
        while LABEL.match(name):
            name = LABEL.sub("", name, count=1).strip()
        names.append(" ".join(name.casefold().split()))
    if any(count > 1 for name, count in Counter(names).items() if name):
        observations.append(DraftFinding("DUPLICATE_PARTNER_NAME", FindingSeverity.WARNING,
            "Partner names repeat after normalizing labels, spacing and case. Verify identity and whether separate roles are intentional.",
            "partner_roles"))
    for entry in draft.timeline:
        matches = ISO_DATE.findall(entry.period)
        dates = []
        try:
            dates = [date.fromisoformat(value) for value in matches]
        except ValueError:
            observations.append(DraftFinding("TIMELINE_INVALID_DATE", FindingSeverity.WARNING,
                "An absolute timeline date could not be parsed. Verify its format and intended date.",
                "timeline", (entry.work_package_id,)))
            continue
        if dates:
            other_years = [int(value) for value in YEAR.findall(ISO_DATE.sub("", entry.period))]
            if max(dates) < reference_date and not any(year >= reference_date.year for year in other_years):
                observations.append(DraftFinding("TIMELINE_DATES_IN_PAST", FindingSeverity.WARNING,
                    "All explicit dates in this timeline entry precede the reference date. Verify whether it is outdated or intentionally historical.",
                    "timeline", (entry.work_package_id,)))
        else:
            years = [int(value) for value in YEAR.findall(entry.period)]
            if years and max(years) < reference_date.year:
                observations.append(DraftFinding("TIMELINE_YEARS_IN_PAST", FindingSeverity.WARNING,
                    "All explicit years in this timeline entry precede the reference year. Verify whether it is outdated or intentionally historical.",
                    "timeline", (entry.work_package_id,)))
    return observations
