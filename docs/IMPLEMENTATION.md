# Technical implementation

## Purpose and system boundary

This repository owns the public Berkeley Council Watch dataset, validation code, static-site source, and GitHub Pages build. It presents a dated, evidence-linked record of public commitments and follow-through.

The public-records archive at [ericdf/berkeley-public-records](https://github.com/ericdf/berkeley-public-records) remains authoritative for source documents and their provenance. Tracker records should point to archive record IDs and exact locations. Do not copy archived source PDFs, captions, transcripts, or other blobs into this repository.

This system does not import nonpublic data or depend on nonpublic sources. Substantive tracker entries must be supported by public records and reviewed before publication. The limited deterministic agenda-intake lane may publish schema-validated official meeting and agenda metadata without human review, under [docs/AUTOMATION_SPEC.md](AUTOMATION_SPEC.md). It must not infer decisions, commitments, or outcomes.

The [Berkeley Decision Project](https://ericdf.github.io/berkeley-decision-project/index.html) publishes analysis, positions, and arguments about systemic issues; its [Substack publication](https://berkeleydecisionproject.substack.com) distributes shorter updates and points readers to full analysis. Berkeley Council Watch presents attributed statements, decisions, evidence, and status. Link analysis to relevant tracker records, and link Substack posts to Council Watch when it tracks the matter.

## Cross-linking and subscriptions

Use the sites as connected entry points with distinct jobs. Add a modest, sitewide header or footer callout on Council Watch inviting readers to subscribe to the [Berkeley Decision Project on Substack](https://berkeleydecisionproject.substack.com) for new analysis. Keep it a simple outbound link; do not embed a signup form or add tracking without a documented need.

When an analysis covers a tracked matter, link from the [Berkeley Decision Project](https://ericdf.github.io/berkeley-decision-project/index.html) to the relevant Council Watch record. Substack posts should link to the full analysis and, where useful, the related Council Watch record. Avoid duplicating full articles or tracker data across the sites; use links so readers can move between analysis, evidence, and follow-through.

## Deployment model

Publish through GitHub Pages as a static site.

- Build pages from version-controlled data and site code. Review substantive tracker claims before publication. The narrowly scoped agenda-intake data may be generated and auto-merged under [docs/AUTOMATION_SPEC.md](AUTOMATION_SPEC.md).
- Do not introduce a server, database, login, write API, site runtime secret, or external runtime dependency for the initial implementation. If the automated archive sync is enabled, keep any GitHub App credential in Actions secrets and out of the build and published site. Internet Archive and Google Drive credentials are never stored in this repository or in the public-records repository: the archive's daily job holds them in a private repository the archive maintainer controls (see the archive's `AGENTS.md`).
- The published site must work using static files. Client-side search or filtering may be added if it does not require a server.
- Keep source data available in machine-readable form as part of the repository or generated site output.
- Build and validate in GitHub Actions. Once deployment is enabled, a commit to the default branch publishes through the existing Pages workflow. Substantive changes to tracker data or pages require review. Only schema-validated agenda-intake metadata within the configured file allowlist may auto-merge after required checks pass.
- Enabling GitHub Pages is a separate, deliberate step taken by the maintainer, not a side effect of the pull request that adds the build or deploy workflow.
- Do not deploy pull-request previews to a public location unless that behavior is deliberately configured and documented.
- Make URLs work under the repository’s GitHub Pages base path. Do not assume the site is served from a domain root.
- Avoid external services and third-party runtime scripts. Any later addition must have a documented purpose and privacy impact.

The build is plain Python using only the standard library (`councilwatch/`, Python 3.11 or later). It has no framework and no third-party dependencies. A generator writes the dataset, and a renderer writes static HTML with relative links only, so pages work under any Pages base path and need no JavaScript. Commands and the dataset are described in [docs/DATA.md](DATA.md). Revisit this choice only when a documented requirement needs something the standard library cannot do.

## Conceptual data model

Use stable IDs and normalized records where one-to-many histories or shared references are expected. The exact filenames may be selected during the first implementation, but the following concepts must remain distinct.

### Source reference

A source reference identifies the evidence behind a claim or status.

Recommended fields:

- Stable source ID.
- Archive repository and archive record ID, when archived.
- Source layer or type where available.
- File path or durable public URL.
- Exact locator: page, section, table, agenda item, transcript timestamp, or minute.
- Retrieval or publication date.
- Optional archived revision or content hash when needed to identify the version reviewed.
- A note about attribution or source limitations.

Prefer an archive ID plus a precise locator over a bare URL. Preserve external official URLs as useful access links. A source reference should make it possible for another reader to find the cited passage.

### Agenda item

An agenda item is a Council matter, not an assertion that the matter is important or problematic.

Recommended fields:

- Stable project ID and source meeting/item identifiers.
- Meeting date, agenda item number, title, and procedural status.
- Authors and co-sponsors as recorded in the official agenda.
- Category or policy area, where useful.
- Amounts and fiscal notes as typed values with source references.
- Staff reports, attachments, annotated agenda, minutes, transcript, or video references.

Retain author and co-sponsor information separately from votes. The annotated agenda, official minutes, and other authoritative outcome records should establish what Council did. A transcript can support deliberation research, with attribution confidence recorded where needed.

### Audit finding and recommendation

Keep the auditor’s finding as an independent baseline. Represent each recommendation separately so that several corrective actions can follow from one finding.

For findings, retain the report ID, finding number, auditor’s wording or faithful summary, scope, qualifications, and source locator. For recommendations, retain the recommendation text, assigned department or officer, management response, promised corrective action, stated due date, and supporting sources.

Track management-reported status separately from status verified against subsequent evidence. Do not silently replace an earlier status; add a dated update with its source.

### Commitment

A commitment is a specific, source-backed future action, deliverable, or result that can be checked later. It may come from an audit response, Council direction, a staff recommendation adopted by Council, a budget or contract action, or another public undertaking.

Recommended fields:

- Stable commitment ID.
- Exact source reference and concise attributed text.
- Responsible actor or department, as identified in the record.
- Commitment type: action, deliverable, deadline, spending condition, or outcome measure.
- Stated due date and success measure, if any.
- Links to the agenda item, audit finding, recommendation, contract, and related commitments.
- Dated status history with source references.

Do not invent a deadline or success measure where the source provides none. Record the field as unknown or not stated.

### Follow-up event

A follow-up event records a dated action, report, decision, or piece of evidence relevant to a commitment or finding. It can include a Council vote, department update, contract amendment, implementation milestone, or verification.

Each event should distinguish:

- What the source directly reports or records.
- Who or what body took the action.
- The date and public source locator.
- The linked commitment, agenda item, audit finding, or contract.
- Any interpretation, clearly labeled as analysis and kept brief.
- Whether the event is reported by the City, independently verified, or unresolved.

An event’s relationship to an audit finding should be classified with a reason, for example: directly relevant, possible recurrence, or not comparable. A relationship alone does not establish a violation or misconduct.

### Contract and financial action

Use a contract entity for the continuing agreement and a separate action record for each award, amendment, extension, waiver, or termination.

Keep these financial concepts distinct whenever the source provides them:

- Original not-to-exceed amount.
- Amendment amount and resulting authorized ceiling.
- Appropriation or funding source.
- Encumbered amount.
- Actual expenditure, by fiscal year where available.
- Contract term and extension dates.
- Procurement method, solicitation or cooperative-purchasing reference, and waiver rationale.

Represent each amount with its type, currency, period, status (proposed, authorized, appropriated, spent, or other source-defined stage), and citation. Do not add amounts from different financial stages or scopes as if they were comparable.

## Status and history

The reviewed records are implemented in `data/tracked/`, described in [TRACKED.md](TRACKED.md).

Every current status must have an as-of date and supporting evidence. Keep status changes as dated history rather than overwriting the only record of what was previously reported.

At minimum, the model should distinguish:

- Not yet due: a stated due date has not passed.
- No due date stated.
- In progress, as reported.
- Delayed, with the stated revised date when available.
- Reported complete.
- Completion verified by cited evidence.
- Cancelled, replaced, or superseded.
- Unknown or no current public update located.

A City statement that work is complete, such as a staff report, management response, or department update, supports “reported complete,” however authoritative its source. “Completion verified” requires evidence independent of that statement: for example, an auditor’s follow-up report, an executed contract or amendment, an adopted ordinance, resolution, or policy, or a published deliverable that can be inspected. Cite that evidence with the status.

If a stated due date has passed and no completion evidence is recorded, the interface may say that the item is past its stated date and that completion has not been verified in the tracker as of a particular date. Do not state that the work was not done without evidence supporting that claim.

## Data organization and rendering

Begin with text-based, Git-tracked records such as JSON or YAML, grouped by record type. Define and version schemas before building large datasets. Separate source facts, project classifications, and computed display fields so each can be reviewed.

Generate overview, matter-detail, audit/recommendation, and contract timeline pages from the same records. Pages should show source links next to factual claims, display the last-reviewed date, and preserve context when filtering or searching. Avoid unexplained composite scores in the accountability site.

Every published page must include a visible, consistent attribution notice in its shared footer: “Original written content by Berkeley Council Watch is licensed under CC BY 4.0. Please credit Berkeley Council Watch, link to this page and the license, and indicate changes.” Link CC BY 4.0 to https://creativecommons.org/licenses/by/4.0/. This notice applies to original written content and original data selection or arrangement only. The site's software code is licensed under MIT. Public records, source documents, quoted or excerpted third-party material, and items marked with separate terms remain subject to their own applicable terms.

Keep the rendered site reproducible from a checkout of the repository. Generated output should not become a second place to edit the data.

## Validation and CI

Provide automated checks for:

- Schema validity and required provenance.
- Unique, stable record IDs.
- Valid foreign-key relationships among items, findings, recommendations, commitments, events, contracts, and sources.
- Valid dates, amount types, and financial arithmetic where totals are explicitly derivable.
- Citation locators that are present and well formed.
- Static build success, accessible page structure, and working internal links.

External links can change or be temporarily unavailable. Report link-check results clearly; do not make a temporary failure rewrite or erase the archived source reference.

For every data change, the Git history must show what evidence was added, what status changed, and why. Substantive public data changes require a reviewable pull request. The agenda-intake workflow may auto-merge only the narrow, schema-validated changes defined in [docs/AUTOMATION_SPEC.md](AUTOMATION_SPEC.md).

## Privacy, security, and licensing

The repository and deployed site are public. Commit only material that is intended for public release and supported by public sources. Never copy unpublished notes, personal information, credentials, or other nonpublic material into the tracker.

Do not add secrets or credentials to code, data, build logs, GitHub Actions artifacts, or site output. A static public site should not need secrets to build or serve its content.

Software code in this repository is licensed under the MIT License. Original written content and original data selection or arrangement are licensed under CC BY 4.0 as described in [CONTENT_LICENSE.md](../CONTENT_LICENSE.md). These notices apply only to rights Berkeley Council Watch has authority to license. Official public records, source documents, quoted or excerpted third-party material, and items with separate terms are not relicensed by these notices; retain citations and follow their applicable terms.

## Initial implementation sequence

1. Confirm repository constraints and choose the static build approach.
2. Define the smallest usable schemas and validate sample records.
3. Create one end-to-end tracked matter with an official source, a specific commitment, a dated follow-up, and a clear evidence-based status.
4. Build accessible overview and detail pages from those records.
5. Add automated validation and a build that produces the site without deploying it.
6. Review the built site’s rendering, citations, status language, and base-path behavior.
7. Enable GitHub Pages deployment as a separate maintainer step, then expand the dataset.

Keep the data model broad enough for any Council item with trackable commitments or follow-through. Use the contracting audit as an initial case, not as the whole product scope: City Auditor Jenny Wong, *City Contracts: Outdated Process Led to Non-Competitive Contracts* (report dated February 19, 2026; presented to Council as Consent Calendar Item 6, March 10, 2026; 13 recommendations). Official copy: https://berkeleyca.gov/sites/default/files/2026-02/2026-03-10%20Item%2006%20City%20Contracts%20Outdated%20Process%20Led%20to%20Non-Competitive.pdf. Cite it by archive ID once the public-records archive holds it.