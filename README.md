# Berkeley Council Watch

**Tracking Council commitments and City follow-through.**

Berkeley Council Watch is a public, source-linked record of what Berkeley’s elected officials and City government said would happen, what they directed, and what the public record shows afterward.

The site makes commitments and follow-through easy to inspect over time. For each tracked matter, it records the statement or decision, who was responsible, any stated deadline or measure of success, later actions, and the evidence supporting the current status.

## What it tracks

The project can follow any Berkeley City Council item where a commitment, direction, spending decision, contract, deliverable, or outcome merits later attention. This includes audit recommendations and management responses, budget and contract actions, Council referrals, implementation deadlines, and other public commitments.

The scope is not limited to audit items. Audits provide a useful starting point because they often identify a problem, recommend corrective action, and record a management response.

## What the site shows

For each tracked matter, Berkeley Council Watch aims to show:

- What was proposed, promised, directed, approved, or reported.
- Who made the commitment or is responsible for carrying it out.
- Any amount, deadline, deliverable, or measure stated in the public record.
- What subsequent Council or City action took place.
- What evidence supports the current status, and when that status was last reviewed.

Statuses describe the evidence available as of a stated date. A missing update is recorded as a gap in the public record, not as proof that no work occurred.

Financial figures retain their meaning. Contract ceilings, appropriations, amendments, expenditures, and delivered results are recorded separately when the sources distinguish them.

## How it relates to other work

Berkeley Council Watch is the accountability tracker. Its job is to put public commitments and follow-through back in view, with links to the underlying record.

The [Berkeley Decision Project](https://ericdf.github.io/berkeley-decision-project/index.html) publishes full analysis, position papers, and arguments about systemic problems that may emerge across tracked matters. Its [Substack publication](https://berkeleydecisionproject.substack.com) carries shorter updates and directs readers to the full analysis. Berkeley Council Watch presents attributed facts, status, and evidence; analysis should link to relevant tracker records, and Substack posts should link to Council Watch when it tracks the matter.

The tracker publishes material supported by public records and reviewed for public release.

## Source records

The authoritative archive for source documents is the public Git repository [ericdf/berkeley-public-records](https://github.com/ericdf/berkeley-public-records). Berkeley Council Watch stores structured accountability data and the code for presenting it. It points to source records in the archive using stable identifiers and precise locations; it does not duplicate archived PDFs or transcripts.

Where possible, citations identify the archive record, page or section, and the relevant date or meeting timestamp. Official records establish what the City said or did. Transcripts and captions can help locate deliberation, but uncertain speaker attribution or wording must be marked and checked against stronger sources where possible.

## Editorial and data standards

- Separate a source’s statement from the project’s description of what happened.
- Attribute commitments and actions to the person, body, or department identified in the record.
- Preserve relevant qualifications, disagreements, changes, and uncertainty.
- Distinguish a reported completion from completion verified by supporting evidence.
- Do not infer misconduct, intent, savings, harm, or legal violation from a pattern alone.
- Record unknown or undisclosed information as unknown; do not fill gaps with estimates presented as fact.
- Keep a dated history of status changes and corrections.
- Make public data and the reasoning behind status labels reviewable.

## Repository contents

This repository contains:

- Structured records for tracked matters, commitments, actions, sources, and financial changes.
- Schemas and validation tools for checking records and their links.
- The public-facing static site, built from reviewed records and published through GitHub Pages.
- Documentation for adding, updating, and correcting entries.

The initial implementation should favor a small, auditable system. The technical architecture and data rules are described in [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md). Instructions for coding agents are in [AGENTS.md](AGENTS.md).

## Status

The site is built from two kinds of data:
- **Agenda records** for every City Council meeting the City lists. They are generated from the public-records archive; see [docs/DATA.md](docs/DATA.md).
- **Reviewed tracked matters.** The first is the City Auditor's 2026 contracts audit; see [docs/TRACKED.md](docs/TRACKED.md).

The historical backfill's candidate pass is built; see [docs/BACKFILL.md](docs/BACKFILL.md). The Pages deploy workflow is built; it publishes once the maintainer switches the Pages source to GitHub Actions (see [docs/DATA.md](docs/DATA.md#deployment)).

## Corrections and contributions

Use GitHub issues to report missing records, broken links, factual corrections, or questions about methodology. Proposed data or code changes should include the public source and exact locator needed to review them.

Software code is licensed under the [MIT License](LICENSE). Original written content and original data selection or arrangement are licensed under [CC BY 4.0](CONTENT_LICENSE.md), subject to that file's scope and exclusions.