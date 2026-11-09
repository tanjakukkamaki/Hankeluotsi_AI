# Local funding relevance — rule version 1

The live-results selector previously sorted by call status and identifier, so an unrelated scientific topic could appear first. The new order uses an explicit local research heuristic. The ranking does not change, invent or certify funding facts. It makes no application or eligibility decision.

## Inputs and privacy

- Primary project text: saved title, development need, expected change and available concept objectives.
- Secondary thematic text: saved target groups, at half the primary weight.
- Source thematic text: the retrieved call title and objectives/description excerpt. Priorities already in that excerpt are included; no absent priority is invented.
- Context: saved geography against the explicit source geography field, and described partner organisation types against explicit source applicant text. Target groups are never assumed to be applicants. The existing project schema does not establish an applicant's legal status.

Everything runs in pure Python on the local machine. No network, LM Studio, cloud AI or database writes occur in the matcher. Existing retrieval still sends the same fixed public requests without project descriptions, keywords or ranking scores. Filters and selection reuse the session snapshot. General programme suggestions retain their separate, unscored topic comparison.

## Scoring and categories

The vocabulary is a small, reviewable English/Finnish dictionary in `hankeluotsi/funding_matching.py`. It recognises selected themes, countries, northern regions and organisation labels; it is not a multilingual semantic model.

1. Each recognised project theme receives its dictionary weight, doubled if present in primary text. Culture/creative work, skills/learning and community development have weight 5; other specific themes weight 4; broad digital/research/innovation terms weight 1. Repetition does not add weight.
2. A shared theme earns its project weight times 1 for title evidence, otherwise 0.8 for source objectives evidence. Theme points are `round(80 × earned / total project-theme weights)`.
3. Known non-art phrases, including **state-of-the-art**, **innovation culture** and **bacterial culture**, do not support cultural matching. Nearby explicit negation suppresses keyword matches. If only broad digital/research/innovation terms overlap, or if the call title has a recognised specialist focus absent from the project and no specific shared title theme, theme points are capped at 24. This limits incidental community references in unrelated energy/nature research.
4. Geography adds 5 for named-country overlap or 10 for named-region overlap. Different recognised names subtract 5 as a manual-check clue, never a rejection. Broad EU membership, subregional eligibility and cross-border rules are not inferred. Exclusion wording prevents positive context points.
5. Explicit partner-type wording adds 10 for overlap, subtracts 5 for differing recognised types, otherwise adds zero. Missing legal/applicant information never receives positive points. This is descriptive context, not proof of applicant eligibility.
6. The score is the component sum bounded to 0–100. It is a heuristic index, not a percentage chance, calibrated model confidence or funding probability.

| Category | Rule |
|---|---|
| High | At least 55 theme points and two specific shared themes. |
| Medium | At least 25 theme points and one specific shared theme. |
| Low | Sufficient text for a preliminary comparison, but neither stronger rule is met. Broad digital/research/innovation matches alone stay Low. |
| Insufficient Information | No recognised project themes, no substantive description and no specific title evidence, or an unconfirmed official source reference. No total score is assigned. |

A description excerpt shorter than 40 characters is treated as missing/substantively insufficient. A missing description or differing named geography/partner conditions caps High at Medium. Scores do not override those category gates. Matched themes, component points, caveats and the rules are available on each card.

**Matching confidence is separate:** Limited for insufficient description, unconfirmed source, unknown current status or an unscored match; otherwise Moderate. Stronger requires two specific shared themes plus positive named geography and partner-type clues. These labels describe the available evidence for a keyword comparison; none confirms eligibility. Unknown geography/applicant conditions always remain human checks even on a High card.

## Source facts and current status

The original frozen `FundingCall` is retained by reference, including its title, identifier, raw/parsed dates, published status, source/evidence URLs and timestamps. The new matcher makes no requests to recheck URLs on reruns.

Successful official retrieval is established by the existing adapters. The matcher additionally checks the source relationship: Aurora's exact official calls page and approved timetable CSV pattern, or a Horizon identifier matching its official topic URL and one of the supported API evidence endpoints. An official-looking domain alone does not suffice. A bad reference is visibly unconfirmed, unscored and assigned unknown **display** status; the original published source status remains intact in the evidence details.

Recognised references do not prove that the remote website is available now or that all requirements were retrieved. The existing conservative date/status checker remains unchanged: conflicting or missing dates and stale snapshots can produce unknown current status. A strong thematic match can still be closed or unknown. The card keeps this separate status, its reason, exact source links and retrieval time visible.

Sorting is category, descending score, current status (open/upcoming/closed/unknown), source, identifier. All categories/programmes/statuses are included initially. A thematically relevant closed call can appear before an unrelated open call. Filters retain access to Low and unmatched results. Empty selections show no results with a recovery message. A changed result catalogue safely repairs obsolete programme/call selections without repeating retrieval.

## Coverage and limitations

Ranking cannot compensate for retrieval coverage. The existing slice contains Aurora's timetable and at most 20 source-labelled open Horizon topics, not every EU call. Aurora includes historical and indicative information. EURA and Business Finland remain programme guidance. Source excerpts may be shortened, and the vocabulary misses synonyms, morphology, implicit intent and some exclusions. A thematic High is not a recommendation to apply. Exact geographic, partnership, applicant and multi-stage submission requirements must be read in the official documents.

The 9 November 2026 source check retrieved 16 Aurora and 20 Horizon records and compared all 36 titles, identifiers, available raw dates and published statuses with their raw official CSV/API responses. The community-arts fixture's Solar Radiation Modification topic was Low (0 points). Cultural-priority Aurora records ranked ahead of it, retaining their closed status. These are dated observations, not a promise about future catalogue results.

## Manual review

1. Refresh the actual app at `http://localhost:8501` (Ctrl+F5). If modules were edited while Streamlit was running, stop it with Ctrl+C and launch from the repository root using `.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1` in PowerShell. Open the URL printed by that terminal.
2. Open a saved **fictional** community arts/digital-skills project, preferably with a concept. Expand **Find Funding Opportunities (optional)** and explicitly choose **Search Live Funding Calls**.
3. Confirm the first record has supporting thematic evidence. An unrelated scientific call must not receive High/Medium from generic research/digital wording alone. If all available calls are Low/unmatched, expect an honest notice rather than invented relevance.
4. Inspect the category, score, confidence, explanation and rule breakdown. Check the separate current status/reason, source title/ID, raw dates, source URLs and retrieval timestamp. Read actual terms on the official page.
5. Try each relevance, programme and status filter, including Low, Insufficient Information and unknown. Select none to check the empty message; reselect options to restore results. General programme guidance remains accessible.
6. Inspect several cached calls/filters: the explicit-search timestamp must stay unchanged. Repeat with a fictional creative-industry and community-development project. Changing the saved project must not display another project's comparison.
7. Open a saved concept again and confirm its text, consistency results and PDF action remain intact. No ranking result is saved to SQLite and no model generation should occur.

Automated offline regressions cover fictional relevance ordering, ambiguity/negation, missing descriptions and requirements, source provenance, conflicting/stale dates, filters, source failures, reruns, refreshes and preserved saved/approved records. Public-source checks are separate from normal pytest.
