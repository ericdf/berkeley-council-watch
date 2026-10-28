# Technical implementation

## Purpose and system boundary

This repository owns the public Berkeley Council Watch dataset, validation code, static-site source, and GitHub Pages build. It presents a dated, evidence-linked record of public commitments and follow-through.

The public-records archive at [ericdf/berkeley-public-records](https://github.com/ericdf/berkeley-public-records) remains authoritative for source documents and their provenance. Tracker records should point to archive record IDs and exact locations. Do not copy archived source PDFs, captions, transcripts, or other blobs into this repository.

This system does not import nonpublic data or depend on nonpublic sources. Public entries must be supported by public records and reviewed before publication.

The [Berkeley Decision Project](https://ericdf.github.io/berkeley-decision-project/index.html) publishes analysis, positions, and arguments about systemic issues; its [Substack publication](https://berkeleydecisionproject.substack.com) distributes shorter updates and points readers to full analysis. Berkeley Council Watch presents attributed statements, decisions, evidence, and status. Link analysis to relevant tracker records, and link Substack posts to Council Watch when it tracks the matter.

## Cross-linking and subscriptions

Use the sites as connected entry points with distinct jobs. Add a modest, sitewide header or footer callout on Council Watch inviting readers to subscribe to the [Berkeley Decision Project on Substack](https://berkeleydecisionproject.substack.com) for new analysis. Keep it a simple outbound link; do not embed a signup form or add tracking without a documented need.

When an analysis covers a tracked matter, link from the [Berkeley Decision Project](https://ericdf.github.io/berkeley-decision-project/index.html) to the relevant Council Watch record. Substack posts should link to the full analysis and, where useful, the related Council Watch record. Avoid duplicating full articles or tracker data across the sites; use links so readers can move between analysis, evidence, and follow-through.

## Deployment model

Publish through GitHub Pages as a static site.

- Build pages from version-controlled, reviewed data and site code.
- Do not introduce a server, database, login, write API, secret, or runtime dependency for the initial implementation.
- The published site must work using static files. Client-side search or filtering may be added if it does not require a server.
- Keep source data available in machine-readable form as part of the repository or generated site output.
- Build and validate in GitHub Actions. Deploy the production site from the default branch after checks pass.
- Do not deploy pull-request previews to a public location unless that behavior is deliberately configured and documented.
- Make URLs work under the repository’s GitHub Pages base path. Do not assume the site is served from a domain root.
- Avoid external services and third-party runtime scripts. Any later addition must have a documented purpose and privacy impact.

The frontend framework and build tool are intentionally undecided. Choose a simple, actively maintained static build approach after inspecting the repository and documenting the choice. Avoid a framework or service whose main benefit is solving a problem the initial site does not have.

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

Every current status must have an as-of date and supporting evidence. Keep status changes as dated history rather than overwriting the only record of what was previously reported.

At minimum, the model should distinguish:

- Not yet due.
- In progress, as reported.
- Delayed, with the stated revised date when available.
- Reported complete.
- Completion verified by cited evidence.
- Cancelled, replaced, or superseded.
- Unknown or no current public update located.

If a stated due date has passed and no completion evidence is recorded, the interface may say that the item is past its stated date and that completion has not been verified in the tracker as of a particular date. Do not state that the work was not done without evidence supporting that claim.

## Data organization and rendering

Begin with text-based, Git-tracked records such as JSON or YAML, grouped by record type. Define and version schemas before building large datasets. Separate source facts, project classifications, and computed display fields so each can be reviewed.

Generate overview, matter-detail, audit/recommendation, and contract timeline pages from the same records. Pages should show source links next to factual claims, display the last-reviewed date, and preserve context when filtering or searching. Avoid unexplained composite scores in the accountability site.

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

For every data change, reviewers should be able to see what evidence was added, what status changed, and why. Public data changes should go through a pull request or an equivalently reviewable Git change.

## Privacy, security, and licensing

The repository and deployed site are public. Commit only material that is intended for public release and supported by public sources. Never copy unpublished notes, personal information, credentials, or other nonpublic material into the tracker.

Do not add secrets or credentials to code, data, build logs, GitHub Actions artifacts, or site output. A static public site should not need secrets to build or serve its content.

Original project-authored text, code, and compilations in this repository are licensed under CC BY 4.0. Official public records, source documents, quoted or excerpted third-party material, and items with separate terms are not relicensed by this notice; retain their citations and follow their applicable terms. Make the licensed scope clear wherever those materials appear alongside project-authored content.

## Initial implementation sequence

1. Confirm repository constraints and choose the static build approach.
2. Define the smallest usable schemas and validate sample records.
3. Create one end-to-end tracked matter with an official source, a specific commitment, a dated follow-up, and a clear evidence-based status.
4. Build accessible overview and detail pages from those records.
5. Add automated validation and GitHub Pages deployment.
6. Review the public rendering, citations, status language, and base-path behavior before expanding the dataset.

Keep the data model broad enough for any Council item with trackable commitments or follow-through. Use the contracting audit as an initial case, not as the whole product scope.