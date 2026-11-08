"""Opt-in public-source checks; never contact services in default pytest runs."""

import os

import pytest

from hankeluotsi.funding_calls import assess_call_status
from hankeluotsi.funding_eu import fetch_horizon_calls
from hankeluotsi.live_funding import fetch_aurora_calls


pytestmark = pytest.mark.skipif(
    os.getenv("HANKELUOTSI_LIVE_FUNDING") != "1",
    reason="Set HANKELUOTSI_LIVE_FUNDING=1 explicitly to contact official public sources.",
)


@pytest.mark.parametrize("fetch", [fetch_aurora_calls, fetch_horizon_calls], ids=["aurora-csv", "horizon-api"])
def test_official_public_call_contract(fetch):
    result = fetch()
    assert result.calls, f"No call records could be verified: {result.notices}"
    assert len({call.identifier for call in result.calls}) == len(result.calls)
    assert any(call.deadline is not None for call in result.calls)
    for call in result.calls:
        assert call.title and call.identifier
        assert call.source_url.startswith("https://")
        assert call.evidence_url.startswith("https://")
        assert call.retrieved_at.utcoffset() is not None
        assert assess_call_status(call)[0] in ("open", "upcoming", "closed", "unknown")
