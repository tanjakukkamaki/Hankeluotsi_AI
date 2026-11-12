# Draft & Review: proposal for owner approval

Prepared during the November planning-quality experiments. **Architecture only: no production stage, prompt, project schema, database migration, UI or exporter is implemented here.** Experimental needs/critique JSON is a benchmark artifact, not a production `ApplicationDraft` or `ReviewReport`.

## Proposed bounded workflow

`Original fictional idea → essential clarifications → expanded draft → deterministic checks → evidence-linked AI critique → proposed corrections → user decisions → recheck/review → explicit approval → approved export`

The current `created → concept_ready → draft_ready → reviewed → approved` state machine remains the starting contract. Clarification and correction handling need explicit design approval before introducing durable fields or tables. Do not silently treat an unanswered question, an AI suggestion or a saved concept PDF as approval of a final application.

| Step | Input / output | Human decision and invariant |
| --- | --- | --- |
| Clarification | Original `ProjectIdea`, supplied evidence and prioritized questions identifying field, gap and why it matters | Ask only essential blockers. Separate unknown, proposed, user-confirmed and externally verified information. Pause when a responsible scope cannot be chosen. Never manufacture answers overnight. |
| Expanded draft | Approved source snapshot, valid concept and actual clarification answers; owner-approved final draft contract | Preserve beneficiaries, geography and constraints. Agree bounded WP/O/A/R/I structures, activity ownership, results, indicators, risks and open questions before implementing. Proposed targets/roles remain provisional until accepted. |
| Deterministic checks | Valid draft and stable reference graph | Run Python checks for IDs, required data and links. A structurally connected graph does not certify the intervention logic or indicator validity. Show findings separately from AI opinions. |
| AI critique | Original source snapshot, current draft and deterministic findings | Fresh reviewing context should cite source/draft field or ID, actual evidence, observation, uncertainty and practical consequence. Same-model critique is role separation, not independent human verification. |
| Suggested corrections | Small field-specific proposals with current value, proposed value, reason and source references | Preserve the original. User accepts/rejects proposals; AI cannot silently change scope, add facts or overwrite stored content. Check that a fix does not remove a necessary activity or introduce a new inconsistency. |
| Recheck and review | User-accepted candidate | Revalidate and rerun deterministic checks. Changes invalidate dependent review/approval atomically. Prevent stale critique and approval from being attached to changed text. |
| Approval and export | Current reviewed candidate and explicit user action | Only a human approves. Lock the approved record; later edits require a new record under the existing immutability rule. Export through the approved-record gate with disclaimer, IDs and original content intact. |

## Contracts to agree before coding

**Clarifications/evidence:** A small versioned structure should distinguish the original fact, the source field, a question, the actual answer, who/what supplied it and its verification status. Do not confuse `partners=null` with confirmed absence of partners. A programme URL alone does not verify an eligibility rule. Decide whether clarification evidence is a bounded sidecar record or approved schema addition; either requires an explicit storage/versioning decision, not a hidden SQLite migration.

**Expanded draft:** Final `ApplicationDraft` fields remain unimplemented. Agree work packages, linked objectives/activities/results/indicators, partner roles, impact reasoning, sustainability, risks and questions in PLANS. Existing generic repository save/approval methods are useful groundwork; benchmark-only draft schemas are not the approved final contract. Do not extend `ConceptPaper` opportunistically with WP, budget or review keys.

**Review findings:** Keep deterministic finding codes unchanged. Proposed semantic findings should identify category, field/ID, exact supporting text, severity, explanation, confidence/uncertainty, suggested change and whether human/source verification is needed. “The indicator does not specify its denominator” is different from a proven unresolved ID. Do not label subjective usefulness as a certified programme requirement.

**Corrections:** Use bounded proposals against a specific source snapshot, with an expected old value to detect stale changes. Avoid a complex document-history feature. A separate proposed candidate and a user decision are sufficient; saving an accepted upstream change must atomically invalidate downstream review/approval.

## Quality controls required

- Needs distinguish the stated gap, its consequences, supplied evidence and missing evidence. Do not invent a baseline to make prose persuasive.
- Objectives describe a feasible change; activities describe the intervention. Outputs, participant outcomes and longer-term impact must not be interchangeable promises.
- Indicators specify unit, unique counting/numerator/denominator, success criterion, collection method and timing. Clearly label proposed targets and unresolved choices. Self-reported satisfaction cannot automatically certify practical competence, safety, ecological impact or clinical effects.
- Clarifying questions must not repeatedly ask for facts already supplied, or block an early concept solely because a detailed budget/baseline is unknown. Ask what is needed to make the next responsible decision.
- A critique's quotes and field references need checking against the source. Its suggested replacement remains untrusted, even when the critique correctly found an error.
- Finnish/English checks cover grammar and meaning in every stage, not only final headings. Preserve keys/IDs and never automatically rewrite previously saved projects when switching language.
- Store original, proposed and accepted material distinctly. Model output cannot approve itself, write directly to SQLite, hide Python findings or submit an application.

## Prioritized implementation sequence

1. **Before prototype submission:** Owner reviews experimental evidence and human-quality limits. Preserve the tested concept workflow; do not rush an untested final-stage workflow into the 22 November demonstration.
2. **Contract/design gate:** Owner approves clarification/evidence handling and bounded final draft/review contracts, compatibility/versioning and acceptance criteria. Freeze a new experiment for any revised prompt or contract.
3. **Draft vertical slice:** Explicit generation with real supplied clarifications, strict validation, linked draft checks and transactional failure preservation. Test regeneration/idempotency and unsupported schema versions before UI exposure.
4. **Review/correction slice:** Evidence-linked review, separate proposed changes, user acceptance/rejection, revalidation and stale-snapshot guards. Include tests where a seemingly helpful revision makes coherence worse.
5. **Approval/export slice:** Explicit approval, immutability and escaped approved Markdown export. Preserve the existing concept PDF feature as a separate draft export.
6. **Final evaluation:** Independently score representative fictional full workflows and both languages; compare approved final contracts with at least the planned first-attempt reliability gate. Follow the existing 4 December feature-freeze and 13 December delivery plan, subject to teacher instructions.

Each slice needs separate owner approval, bounded offline tests and a real application check. The proposed sequence does not claim that any missing production stage has been completed.

## Human expert review remains necessary

Domain experts must judge whether the need is credible, proposed change matters, activities are deliverable, evidence supports attribution, measurement is appropriate and the application meets an actual programme's requirements. The owner must resolve missing facts and accept scope/corrections. AI-assisted scores and same-model critiques are not a substitute for that validation. This application must not certify eligibility or guarantee funding.
