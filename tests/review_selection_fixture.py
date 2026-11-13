"""Convert known review fixture citations to the model's source-selector contract."""

import json


def selected_review_fixture(review, user_input):
    packet = json.loads(user_input.split("\nSOURCE_PACKET:\n", 1)[1])
    entries = packet["evidence_catalogue"]["entries"]
    result = dict(review)
    result["findings"] = [{"evidence_id": next(e["evidence_id"] for e in entries
        if e["reference"] == f["reference"] and f["evidence_quote"] in e["quote"]),
        "observation": f["observation"], "suggestion": f["suggestion"], "severity": f["severity"]}
        for f in review["findings"]]
    return result
