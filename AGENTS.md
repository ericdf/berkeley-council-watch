# Instructions for coding agents

## Read first

Before changing code or data, read:

1. README.md
2. docs/IMPLEMENTATION.md
3. Any more specific AGENTS.md files in the directory you will edit

Treat README.md and docs/IMPLEMENTATION.md as the project contract. If the requested change conflicts with them, explain the conflict and propose a small update to the relevant documentation.

## Product boundaries

- This repository builds the public Berkeley Council Watch accountability tracker and its static GitHub Pages site.
- The tracker records what was said, directed, promised, and later documented. The [Berkeley Decision Project](https://ericdf.github.io/berkeley-decision-project/index.html) publishes analysis and positions; its [Substack](https://berkeleydecisionproject.substack.com) distributes shorter updates. Link relevant analysis and Substack posts to Council Watch records when available.
- The public-records archive is authoritative for source documents. Link to its stable record IDs and precise locators; do not duplicate archived documents here.
- Do not import or publish nonpublic notes, analysis, or data. Public tracker entries must be grounded in public records and deliberately reviewed for publication.
- Track any relevant Council item, not audits alone. Audits are one source of findings, recommendations, and explicit follow-up commitments.
- Keep the initial architecture static and simple. Do not add a database, server, account system, write API, analytics service, or external runtime dependency without a documented requirement.

## Evidence and language

- Every factual public claim must have a reviewable source reference and exact locator.
- Preserve the difference between what an official source says, what Council decided, what staff later reported, and what the evidence independently verifies.
- Keep amounts labeled by financial stage: proposed, authorized, appropriated, encumbered, spent, or delivered. Never combine unlike stages.
- Preserve dates, attribution, uncertainty, qualifications, corrections, and disagreement.
- Do not invent commitments, owners, dates, outcomes, contract histories, or procurement findings.
- A missing public update supports “no update located as of [date]”; it does not establish that no work occurred.
- A possible relationship to an audit finding is a research classification, not proof of misconduct, illegality, waste, favoritism, or failure.
- When analyzing transcripts or captions, treat them as fallible. Keep speaker attribution confidence and corroborate important wording with authoritative records or video where possible.
- If evidence is insufficient, mark the point unresolved and state what record would resolve it.

## Data and code changes

- Preserve stable IDs and existing relationships. Do not silently recycle or renumber IDs.
- Add or revise schema validation when data structures change.
- Keep status history dated and sourced; do not erase prior statuses when new evidence arrives.
- Store source references with archive IDs and locators wherever possible. External official links can supplement archive references.
- Keep source facts, editorial classifications, and computed display values distinct.
- Make changes small enough to review. Update documentation when behavior, schema, build steps, or deployment changes.
- Inspect the existing project scripts before selecting commands or adding dependencies. Prefer established conventions in this repository.
- Do not introduce credentials or secrets. Public static builds should not require private access.
- Do not configure a custom domain or expose a new production destination unless that exact deployment change is requested. GitHub Pages is the intended host.

## Static site and accessibility

- Ensure pages work when served from the GitHub Pages project base path, including direct navigation to detail pages.
- Include a visible CC BY 4.0 attribution notice in the shared footer on every published page. Use consistent wording: “Original written content by Berkeley Council Watch is licensed under CC BY 4.0. Please credit Berkeley Council Watch, link to this page and the license, and indicate changes.” Link “CC BY 4.0” to https://creativecommons.org/licenses/by/4.0/. The code is MIT-licensed; the footer notice applies to original written content and original data selection or arrangement only.
- Make clear on pages that include official records or third-party material that those materials may have separate terms and are not relicensed by the CC BY 4.0 content notice.
- Use semantic HTML, keyboard-accessible controls, visible focus, readable contrast, responsive layouts, and descriptive link text.
- Keep core facts and citations available without client-side JavaScript where practical.
- Do not hide caveats, status dates, or source links behind hover-only interactions.

## Verification

For implementation changes, run the relevant formatter, schema/data validator, build, and tests defined by the repository. Report exactly what ran and any failures. Do not claim a check passed unless it was run successfully.

For content-only updates, verify IDs, citations, locators, dates, amounts, and linked records against the cited public sources. Avoid unrelated code or data changes.

## Review and publication

- Treat the repository as public at every stage. Review diffs for private or personal information before committing.
- Keep generated output reproducible from committed source data and code.
- Changes to public data must make clear what changed and which public evidence supports it.
- Do not deploy from an unreviewed branch or enable pull-request previews at a public URL unless explicitly requested.
- If a task could publish a disputed or sensitive claim, surface the evidence and uncertainty in the proposed change rather than silently resolving the judgment yourself.