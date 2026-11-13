# Mistral request diagnosis — 12 November 2026

## What is established

The reported UI message, “Mistral rejected the request or is unavailable,” originated from a broad non-success HTTP branch. It discarded the status along with the body, so the historical message alone cannot distinguish an invalid request, missing model, account billing issue, permission failure or service outage. No specific historical API/schema/model root cause is asserted.

In this development process, `MISTRAL_API_KEY` is absent and no valid `MISTRAL_MODEL` is configured. Only key-presence and safe model metadata were inspected; no key value was printed or stored. A key in the owner's separate PowerShell does not automatically exist in this process. No account/model-list request, paid generation request or live authentication test was made during this task.

The adapter already uses the documented fixed endpoint `https://api.mistral.ai/v1/chat/completions`, bearer authentication, messages, bounded `max_tokens`, temperature and JSON-schema response mode. Official documentation supports this structure. There is no recorded evidence establishing that the current Pydantic-generated schema is incompatible with the owner's exact model/account, so the implementation does not strip schema constraints, switch formats silently or guess a different model.

## Targeted corrections

`CloudError` now retains only a bounded numeric `http_status`, when available. Fixed error categories distinguish:

| HTTP status | Safe category / next check |
| --- | --- |
| 400 / 422 | Request/schema/parameters need checking; the exact field is unknown without a separately reviewed diagnostic |
| 401 | Authentication failure |
| 402 | Account billing or credits require checking |
| 403 | Workspace/model access or permissions require checking |
| 404 | Requested resource/model identifier/access requires checking |
| 408 / 504 | Timeout reported by the service |
| 413 | Request size requires revision |
| 429 | Rate limit; no automatic retry |
| Other 5xx | Server failure; check service state |
| Other non-2xx, including redirects | Generic HTTP failure; redirect not followed |

These are interpretations of the returned status, not proof of an account's exact balance or a programme requirement. Responses are not parsed or echoed on HTTP failure, and neither headers nor arbitrary exception strings are logged. Existing network/TLS, timeout, malformed-envelope, empty/invalid JSON, schema and incomplete-output handling remains. Unexpected errors are still sanitized. The actual API key remains environment-only and server-echoed key text is redacted on successful transport.

`MistralClient.generate` additionally accepts explicit `max_tokens` and `timeout_seconds` for draft/review calls. Defaults remain **512 / 120 seconds** for the existing concept flow. Allowed bounds are integer 128–8192 output tokens and 1–600 timeout seconds; booleans and out-of-range values are rejected before a request. Output JSON also rejects `NaN`/`Infinity`, which are not JSON numeric values, before Pydantic validation. No repair request or automatic provider fallback was introduced.

## Offline evidence

The focused mock suite covers the fixed endpoint/request/schema, environment isolation, key/consent absence, both direct and factory consent enforcement, all new HTTP categories, sanitized secret-bearing exceptions, ignored provider usage details, malformed JSON/envelopes, nonstandard numeric constants, schema errors, truncation/unknown finish, size limits, budget bounds and explicit draft budgets. Benchmark/report/blind-review compatibility is retained; human scores remain null and tests do not contact providers. Final commands/results are recorded in the main development log.

## Exact remaining verification

1. Launch Streamlit or the benchmark from the **same PowerShell process** where both environment variables are configured. Run the existing no-generation preflight first; do not print the key or environment dump.
2. After owner approval of read-only account access, verify the exact configured model against the account's model inventory. A valid-looking identifier does not establish access or schema support.
3. Verify current pricing, account balance, privacy terms and a bounded input/output cost ceiling before approving one fictional cloud smoke test. None is established by the environment-presence check.
4. Inspect the new safe error category and numeric status if that approved smoke fails. A 400/422 points to request/schema/model-specific constraints, but does not identify the offending field by itself. Do not remove validation blindly or paste raw provider bodies containing project text/credentials into public logs.
5. Confirm a normal finish reason, strict Pydantic validity, expected output language and preserved local state. Check actual token usage/billing separately. Timeout or client failure does not prove that server processing/billing did not occur.

No successful live Mistral repair, account access, model availability or paid benchmark result is claimed. No credential loader, cloud default, retry loop, model substitution, dependency or unrelated feature was added.

Official references checked for this diagnosis: [Chat Completion API](https://docs.mistral.ai/api), [custom structured outputs](https://docs.mistral.ai/inference/conversations/structured-output/custom). Existing secure shell instructions remain in [mistral_setup.md](mistral_setup.md).
