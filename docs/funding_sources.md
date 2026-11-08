# Funding Opportunities Research — first slice

Official information reviewed on **8 November 2026**. General programme guidance is paraphrased in `hankeluotsi/funding.py`. It is not a list of current calls. The owner authorized this optional scope addition after the PR6 consistency changes were committed; PR7 is not started.

## Source investigation

| Source | Official evidence | Retrieval decision |
|---|---|---|
| EURA 2021 | [Official system](https://eura2021.fi/), [public call notices](https://eura2021.fi/hakuilmoitukset/) | The public call page returned a JavaScript shell in direct retrieval. Search-index call tables are not fresh evidence. No documented public call API was located in this bounded investigation. Provide three programme guides and the official calls link. |
| Interreg Aurora | [Programme](https://www.interregaurora.eu/about-us/), [priorities](https://www.interregaurora.eu/about-us/programme-specific-objectives/), [area](https://www.interregaurora.eu/programme-manual/apply-for-a-project/programme-area/), [partners](https://www.interregaurora.eu/programme-manual/apply-for-a-project/eligible-partners/), [calls](https://www.interregaurora.eu/projects/calls-for-applications-2/) | Public HTML guidance is available; no documented public call feed/API was located. Use a programme guide. Northern regional coverage and Sápmi do not imply whole-country eligibility. Call-specific terms and manual exceptions require human review. |
| EU Funding & Tenders Portal | [About](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/about), [official API documentation](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis), [calls](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals) | A documented public search API exists. A URL-encoded test request ignored filters and returned unrelated event records; a multipart test returned HTTP 500. No response was treated as a funding call. Omit the API adapter until the filtered request and response contracts are verified. The official static topic list includes historical entries and cannot establish current status. |
| Business Finland | [Funding services](https://www.businessfinland.fi/en/services/funding/), [company guidance](https://www.businessfinland.fi/en/About-Us/how-we-help-companies/Funding-services-for-companies/) | Public funding-service HTML is available; no documented public calls API/feed was located. Use a general guide and official links rather than infer universal requirements from one instrument. Business Finland funding is not necessarily EU funding. |

EURA programme themes are supported by Commission overviews: [ERDF/EAKR](https://commission.europa.eu/funding-and-tenders/find-funding/eu-funding-programmes/european-regional-development-fund-erdf_en), [ESF+/ESR+](https://commission.europa.eu/funding-and-tenders/find-funding/eu-funding-programmes/european-social-fund_en), [JTF](https://commission.europa.eu/funding-and-tenders/find-funding/eu-funding-programmes/just-transition-fund_en). Actual Finnish regional and applicant conditions remain call-specific. Some `rakennerahastot.fi` pages returned HTTP 403 during research; no access restrictions were bypassed.

## Runtime behavior and evidence dates

- Offline mode returns six frozen, versioned programme records. `call_title` and `application_dates` are null; `status` is `unknown`. A guide is never represented as an open call.
- `guidance_verified_on` records the manual source review date, not the time the user clicked search. These guides may become outdated.
- Optional live retrieval makes one GET per fixed public programme page (four total, sharing EURA for three funds). Only HTML title/description metadata is read. No query strings, project text, keywords, model calls, credentials or POST requests are sent by this feature.
- `information_retrieved_at` is a UTC timestamp only for a successfully fetched usable page description; `retrieved_from_url` identifies that page. Page metadata is displayed separately, as plain text. It does not update the reviewed summaries or verify calls, terms or completeness.
- The retriever retains normal TLS certificate validation, refuses redirects, limits each page to 1 MB (both transferred and decoded gzip content), uses a five-second socket timeout and does not retry. Source errors and JavaScript shells produce labelled fallback guidance. A changed official URL may require an explicit future maintenance update.
- During investigation the default Python trust store rejected the Portal API certificate chain. A separate diagnostic using the already installed trusted CA bundle succeeded with TLS validation enabled. No certificate checks or security settings were disabled. The runtime page retriever keeps the standard trust configuration and falls back on certificate errors.
- Search results are temporary session data for the selected saved idea, not durable funding records. Reruns reuse them; a different project/idea is not shown the previous comparison. SQLite and approved project content are not changed.

## Comparison limits

`compare_locally` matches exact token aliases from the small `TOPICS` vocabulary between the saved idea and reviewed programme objectives. Its topics include innovation, digital, skills, employment, inclusion, green transition, culture, tourism, research, SMEs, international growth and cross-border cooperation. Some English and Finnish variants are included; stemming, translation, semantic inference and comprehensive language support are not implemented.

The output lists shared topics in a fixed order. It does not rank eligibility or calculate a suitability percentage. No overlap means only that this vocabulary found no overlap. Geography, organisation type, partnerships, dates and programme conditions require manual checking. The Portal guide covers many programmes and is intentionally nonspecific. Matching does not use live page metadata as trusted programme facts.

## Validation

Default pytest tests are offline, using fictional projects and mocked retrieval. Live checks are separate and never needed to start the app, compare programme guides, generate a concept or run the test suite. The session's commands/results and remaining limitations are recorded in `development_log.md`.

The finished retriever was checked separately against all four fixed pages on 8 November 2026: Aurora and Business Finland returned usable descriptions; the Portal produced a recoverable certificate-chain error. EURA returned gzip content, prompting bounded gzip support; a focused recheck decoded its page successfully but found no programme description, so its three fund guides correctly remain fallbacks. No call-level facts or project data were involved in these checks.

Before a future call-level adapter is added, verify its documented request and response, map dates/timezones and statuses with evidence, test stale/malformed data and preserve field-level unknowns. That is a separate owner-reviewed task.
