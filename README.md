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

The policy site is where we publish analysis, position papers, and arguments about systemic problems that may emerge across tracked matters. It may cite Berkeley Council Watch records, while the tracker presents attributed facts, status, and evidence.

The private Berkeley Council Scorecards repository is separate. This public repository does not read from it or publish its contents automatically. Any material developed privately must go through deliberate public review and be supported by public sources before appearing here.

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

This repository is being established. Its purpose and evidence standards are defined here; the data model and site implementation will be developed and reviewed incrementally.

## Corrections and contributions

Use GitHub issues to report missing records, broken links, factual corrections, or questions about methodology. Proposed data or code changes should include the public source and exact locator needed to review them.

See [LICENSE](LICENSE) for the license applying to this repository’s contributions.