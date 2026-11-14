# Optional Mistral Cloud: setup and review

Initially prepared 12 November 2026 on `feature/mistral-integration`. This is an offline-tested foundation, **not a completed live integration or model-quality comparison**. No paid request was made. Local Qwen remains the default, with no automatic fallback. Current13November prompt versions, checks, safe one-call command and exact same-PowerShell verification are in the [Finnish readiness report](mistral_readiness.md); the original foundation notes below are historical where marked. Persisted data contracts remain unchanged.

## Secure Windows configuration

Use a key from your own Mistral account and an owner-approved model/budget. Check current model availability, prices and data-processing terms before a cloud request. No regional residency or confidentiality certification is claimed.

Open PowerShell in the project folder. Set variables only for that shell and launch the app from it. Prompt for the key without displaying it or putting its value in command history:

```powershell
$mistralSecret = Read-Host 'Mistral API key' -AsSecureString
$mistralPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($mistralSecret)
try {
    $env:MISTRAL_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($mistralPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($mistralPointer)
    Remove-Variable mistralSecret, mistralPointer
}
$env:MISTRAL_MODEL = Read-Host 'Exact approved Mistral model identifier'
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Environment variables remain readable by the process/children; they are not an encrypted credential vault. Never print the environment, store the key in source or project fields, or share diagnostics containing it. No dotenv loader or key-entry field was added. Blank key/model disables cloud generation. The model has no implicit default; prefer a verified versioned identifier over a moving `latest` alias. Account access remains unverified until an owner-run request.

After stopping the app with Ctrl+C, close the shell or clear its variables:

```powershell
Remove-Item Env:MISTRAL_API_KEY, Env:MISTRAL_MODEL -ErrorAction SilentlyContinue
```

## Selection and fictional smoke test

In **New project idea / Uusi hankeidea**, choose **Local Qwen (default) / Paikallinen Qwen (oletus)** or **Mistral Cloud (optional) / Mistral-pilvipalvelu (valinnainen)**. Mistral uses the same compact concept input and512-token limit as Qwen. Current concept instructions are version concept_v2; the historical A/B/C experimental recipes remain separate. Interface language controls labels and requested output language, never saved text. Draft/review provider and cost consent are inside Advanced options; each stage needs fresh source-bound cloud consent.

Mistral shows an external-processing/cost notice. Confirm that **all entered data is fictional**, cloud processing is accepted and the submission may incur charges. Generate stays disabled until configuration and consent are present. Each call requires explicit form submission; choosing a provider, rerunning, changing language and opening saved projects do not send data. Switching providers resets consent. There is no silent fallback.

Owner-run smoke test after privacy/budget approval (not performed during implementation):

1. Use a fully synthetic idea, such as ten fictional volunteers practising accessible online events in an invented village. Review every field; exclude all real employer/partner/person/confidential information.
2. Select Mistral, check the displayed model, confirm consent and click Generate **once**. This real request may be billed.
3. Inspect the concept, model/prompt/time message, language and deterministic findings; reopen after restart. Valid JSON does not establish good planning quality.
4. Rerun, change language and reopen the record; confirm no additional API calls in your account dashboard. A timeout does not prove server processing or charging stopped: check before resubmitting.
5. Select Local Qwen and test a separate fictional idea with LM Studio running. Existing saved projects must remain unchanged.

The idea is saved locally before generation. Failure may leave a new idea-only record; it never replaces an existing concept. The adapter cannot write SQLite, approve or export. Existing approval immutability is preserved by the unchanged repository.

## Transport, privacy and errors

The adapter uses the fixed documented HTTPS chat-completion endpoint, bearer auth, JSON-schema output and directly declared `httpx2==2.16.0`. The existing direct TLS import also has `certifi==2026.10.23` declared. These versions were verified locally; no Mistral SDK or package installation was added. There are no tools, redirects, environment proxies or automatic retries (`HTTPTransport(retries=0)`). Only submitted idea/prompt/schema goes to Mistral; saved projects are not read by the adapter. Credentials come from the environment at call time and are not logged/serialized. A server-echoed key is redacted.

Fixed bilingual errors distinguish consent/configuration, authentication, rate limits, network/TLS failure, timeout, HTTP rejection, invalid envelope/JSON/schema and incomplete output. HTTP bodies and raw exception strings are not displayed. The actual production transport now preserves bounded, sanitized provider code/parameter/message fields in CloudError; see the current [transport diagnosis and test results](mistral_diagnosis.md). Unknown/incomplete finish reasons cannot produce saved cloud concepts. One request per invocation, no repair retry. The 120-second timeout applies to HTTP phases, not a strict total deadline. A 1 MB response check happens after buffering, not as a streaming memory bound.

Do not enable verbose third-party HTTP tracing with real keys. Fictional-data consent is a human assertion; software cannot prove arbitrary text is synthetic. No cloud residency or retention promise is inferred from the provider being European. TLS verification uses library defaults; proxy environments may need separately reviewed configuration, never disabled certificate validation. Tokens are recorded when reported; usage details are not assumed to establish billing.

## Comparison and remaining verification

Follow the [implemented collector procedure](model_comparison_plan.md#implemented-cloud-collector--12-november-2026). The existing frozen manifest enforces identical synthetic cases/messages/schema/settings. Cloud collection requires `--execute-cloud --fictional-only --accept-costs`; no project database is read. Blinded review hides provider metadata in a separate private key, but outputs may self-identify. Human scores stay null until supplied by a person.

Current milestone, 14 November: the owner reports working Large 4 authentication and live text generation with a valid key, usage of 26 prompt / 32 completion / 58 total tokens and approximately 1.45 seconds for the short probe. Completion was reported as incomplete at the 32-token cap; the exact original finish reason was not supplied. See [updated smoke diagnostics and the prepared 256-token test](mistral_connectivity_2026-11-14.md). No new live request was made by the agent.

Still unverified: complete short-response success with the new cap, exact-model production schema support, per-stage reliability/latency, actual billing and planning quality. The existing Streamlit process must inherit the working key/model from its launching shell; its current credentials were not inspected. A paired study and human rubric ratings remain necessary. The adaptive A/B/C journals are preserved and are not interchangeable with this single-stage manifest. Exact local GGUF/runtime configuration also needs owner evidence. No winning model or improved production prompt is claimed.

Final automated results and code-review findings are in the [development log](development_log.md). Slow-call UX, browser layout/accessibility of the new controls and live cancellation behavior remain manual checks; synchronous AppTest cannot click during a running request. No commit/push is included.

Official sources checked 12 November 2026: [Chat API](https://docs.mistral.ai/api), [custom structured outputs](https://docs.mistral.ai/inference/conversations/structured-output/custom), [account console](https://console.mistral.ai/).

## Separate code-review pass

Codex reviewed the completed diff after the initial adapter/UI tests, separately from implementation. This was self-review, not an independent human audit. Findings and disposition:

| Area | Finding / disposition |
| --- | --- |
| Secrets and errors | Replaced raw transport exception exposure with fixed categories, including unexpected library errors; added a secret-bearing RuntimeError test. Bearer token is environment-only; response echo is redacted. No global logging changes. |
| Consent / routing | Service and transport enforce both boolean confirmations; UI also disables unready generation. Provider switch clears consent. No key/model preflight causes a network call. No automatic fallback. |
| API compatibility | Confirmed documented HTTPS endpoint, schema output and request fields. Ignore extra usage-detail fields while validating known counts. Live model/account support remains unverified. |
| Generation metadata | Corrected the successful cloud result to retain the verified `stop` finish reason instead of the shared result type's default `unknown`; added an explicit regression assertion. |
| Benchmark errors | Added detailed error_type for JSON/schema/incomplete failures as well as transport categories; kept existing Reply/results contracts compatible with blinded review. |
| Maintenance / scope | Minimal Protocol and factory retain unchanged local client; common prompt builder and benchmark runner reused. Removed unused app import. No new dependencies, prompt/data/schema migrations or Draft & Review code. |
| UI / persistence | Fixed language-sensitive selectbox formatting to use captured labels rather than a runtime lambda; AppTest covers FI/EN submission, switch-consent reset, failure preservation and reruns without calls. |
| Remaining limits | Human fiction assertion, imperfect blinding, no live/visual/slow-call audit, buffered response size check and phase timeout remain documented; not represented as solved. |

Regression coverage includes the complete existing offline suite, unchanged repository/approval tests, and mocked paired-provider packet generation. Human review and a separately authorized fictional live smoke test remain release gates; the work is ready for owner review, not certified production deployment.

Final reviewed-source verification: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` with live funding disabled, a unique temporary default database and bytecode writes disabled: **480 passed, 2 skipped in 21.06 s** (41 additional cases relative to the 439-test baseline). Skips are opt-in public-source tests. `git diff --check` and a separate scan of new text files passed. SHA-256 comparison confirmed unchanged original SQLite files, prompts/schemas, local client/config, repository, PDF/funding/consistency/design files and existing benchmark artifacts. No real Mistral output or human score was created.
