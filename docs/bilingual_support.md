# Finnish and English support

Choose **Suomi** or **English** in the top-right application header. English is the default for a new session. The language selector remains visible on mobile. Session state keeps the selection during reruns; it is not stored in SQLite or applied automatically to another browser session.

## Translation boundary

`hankeluotsi/i18n.py` is the central dictionary for application labels, notices, explanatory messages, workflow and status labels, disclaimers, and PDF labels. English source strings are keys; Finnish values retain the same named placeholders. The dictionary tests enforce placeholder parity and check registered UI literals. Known system-message templates localize derived explanations without changing machine codes or identifiers. Unrecognised technical diagnostics retain their original text with a localized error context.

Raw saved titles, idea fields, concept bodies and JSON are never passed to translation helpers. Switching language does not save, regenerate, translate or approve a project. English content can be viewed with Finnish labels, and Finnish content with English labels. The saved title `High`, for example, remains `High` rather than becoming a translated relevance category.

Official funding names, titles, descriptions, requirements, identifiers, links and raw dates remain source evidence in their original language. A visible notice explains this. Application-owned funding labels, statuses, matching explanations, filters and known source-failure notices are localized. Existing funding logic, retrieval requests and scores are unchanged. Neither project data nor language-selection data is sent to funding services.

## State and generation

Translated dropdowns use locale-specific UI keys so their option labels refresh correctly in a real browser. A language-change callback carries the canonical selected project/call IDs and relevance/status filter values to the new widgets. Cached funding results use the same project/idea snapshots in both locales; changing language does not trigger retrieval. Ordinary input keys and the underlying project/schema identifiers retain their existing meaning.

The existing concept input adds only a short instruction to produce human-readable fields in **Finnish** or **English**, retaining JSON field names, schema version and O/A/R/I identifiers. Base prompt templates and `concept_v1`, LM Studio configuration, provider/client and validation are unchanged. New results must still satisfy the original `ConceptPaper` schema. Translated JSON keys are rejected rather than silently repaired. A failed generation preserves valid saved state.

Language is not added to stored records. Consequently, the original document language is not inferred from a database field. Pydantic verifies structure, not linguistic quality; the model may still need human language review. The two successful local-language checks are smoke observations, not the required multi-attempt model benchmark.

## PDF

PDF headings, reference labels, disclaimer, metadata subject and page numbering follow the selected interface language. All original title/body text and IDs remain unchanged. The previous A4 spacing and indicator/method grouping remain in place, using the existing embedded Unicode fonts. A mixed-language PDF is intentional when the interface language differs from the saved content.

The two fictional review PDFs contain the **same Finnish body text**:

- [Finnish labels and disclaimer](qa/bilingual/concept-fi.pdf)
- [English labels and disclaimer](qa/bilingual/concept-en.pdf)

Both were rendered and visually inspected as one-page A4 documents, including `Ä`, `ä`, `ö` and `å`, unchanged O/A/R/I references, grouped measurement methods and Sivu/Page numbering. Existing font tests also cover `Ö` and `Å`.

## Manual review

1. Open **http://localhost:8501** and reload with **Ctrl+F5**. This workspace's stale IPv4/IPv6 app instances were replaced with one fresh localhost process so the selector is available. Existing project data was retained. After later module changes, restart from the repository root using `.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=localhost --server.port=8501`.
2. Open an existing English project. Switch to Suomi and confirm the same project stays open, labels change and its saved English text does not. Switch back. Repeat with a Finnish project; an approved record must retain its content and approval timestamp.
3. Inspect the input form, workflow, concept headings, consistency findings, PDF button and disclaimers. Machine finding codes, JSON keys and IDs stay unchanged. At 390 or 320 px, confirm the header selector is still visible with no document horizontal overflow.
4. For new fictional generation, select the desired language **before** submitting the form. Keep LM Studio available at localhost:1234 with the configured Qwen model. Inspect the validated concept and reopen it after changing interface language; content must remain original.
5. Download a PDF in each interface language. Inspect headings, disclaimer, page numbers, Finnish characters and source content. Language switching should not translate the saved body.
6. Open funding research. Load offline programme guidance, switch languages, and confirm the six cards remain without another fetch. Live search is still a separate explicit action. Inspect matching/filter labels; official call content remains original. Selection/filter changes and language switches must not start generation or refresh the retrieval timestamp.

Actual browser verification used the normal `localhost:8501` app and a separate `127.0.0.1:8513` preview with fictional data. Both interface languages, saved selection, offline guides and emulated widths 1440/820/390/320 px were checked. Local Qwen produced one validated fictional concept in each requested language with O1/A1/R1/I1. The preview used a temporary database; those generated examples did not enter the normal workspace database.

## Limits

No existing content or official source text is automatically translated. Arbitrary backend diagnostics and framework/browser-native controls can remain in their original language. The English/Finnish matching vocabulary is unchanged and has its existing coverage limits. Language quality remains model-dependent; no language classifier, cloud translation, expanded funding coverage or formal accessibility certification was added. Physical mobile devices, full screen-reader coverage and multi-attempt bilingual model benchmarking were not tested.
