# Tracked matters: reviewed accountability records

`data/tracked/` holds the records people write and review: what was committed, by whom, and what the
record shows since. They are never generated or auto-merged. Every change goes through a reviewed pull
request (IMPLEMENTATION.md). `python3 -m councilwatch validate` checks them together with the
agenda-intake data, and CI runs it on every PR.

## Files

The schemas are in `councilwatch/schema/`.

| File | One record per |
|---|---|
| `sources.json` | Source document: issuer, title, date, kind, City URL, archive id and link when archived, fingerprint |
| `matters.json` | Tracked matter: title, the agenda items it appeared on, qualifications stated by the source, last-reviewed date |
| `findings.json` | Audit finding, with the heading as printed |
| `recommendations.json` | Audit recommendation: the text as printed, who it is addressed to, and management's response (position, implementation date and corrective action plan, all as printed) |
| `commitments.json` | Specific, checkable future action: the source's words (`statement`), who is responsible, the date as stated, and a dated status history |
| `events.json` | Dated action, report or decision, linked to the commitments and recommendations it bears on |

**Citations.** Every claim carries citations: a `source_id`, an exact `locator` (a PDF page, an agenda
item or section), and a `quote` where the wording matters. A quote is copied exactly. The validator
rejects line-wrap artifacts such as a broken hyphen.

**Source words and project words are kept apart.** `statement`, `text`, `heading`, `quote` and the
management-response fields are the source's words. `label`, `description` and `basis` are the
project's, written as plain description, never characterization.

## Statuses

Each commitment has a `status_history`. An entry is never edited away; new evidence adds a new entry.

| Status | Rule |
|---|---|
| `not_yet_due` | A stated date or period has not passed |
| `no_due_date_stated` | The source states no date (for example "To be determined") |
| `in_progress_reported` | The responsible party reports the work under way |
| `delayed` | A stated date passed and the source says so, with a revised date when one is stated (`revised_due`) |
| `reported_complete` | The responsible party reports the work done. A City statement of completion supports this status and no higher, however authoritative the speaker |
| `completion_verified` | A record independent of that statement shows it done. The validator requires a citation to a source of kind `auditor_follow_up`, `executed_contract`, `adopted_legislation` or `published_deliverable` |
| `cancelled_or_superseded` | The source records the commitment withdrawn or replaced |
| `unknown_no_update_located` | No update was found. The entry must say what was `searched`; the site shows it. It never means the work was not done |

## Adding a matter

1. Add the sources first, with the archive id when the archive holds the document and the City URL
   otherwise.
2. Prefer scripts for structured text: the contracts-audit recommendations were extracted from the PDF
   with `pdftotext`, not retyped.
3. Record what the source says, with locators. Leave unknown fields `null`.
4. Before writing `unknown_no_update_located`, search, and record exactly what was searched.
5. Run `python3 -m councilwatch validate` and `python3 -m unittest discover -s tests`, build the site, and
   check the matter page. Open a PR.

## The seed: City Contracts audit

`contracts-audit-2026` covers the City Auditor's *City Contracts: Outdated Process Led to
Non-Competitive Contracts* (February 19, 2026; Council Consent Item 6, March 10, 2026).
- **Recommendations:** all 13, with management's responses.
- **Commitments:** the 12 corrective action plans, plus the Council-approved City Manager report-back.
  Recommendation 1.2 has none: management's response, date and plan are all "To be determined".
- **Statuses:** as reported by management in the audit. The audit notes the Auditor had not confirmed
  implementation.
- **Two statuses updated to October 28, 2026**, from a search of every Council annotated agenda from
  March 10 to October 13, 2026 and the October 27 packet index:
  - the City Attorney's legal-services contract report, due April 30, 2026, which was not located;
  - the City Manager's report-back, due in Fall 2026, which is not yet due.

The audit report itself is not yet in the public-records archive, so it is cited by its City URL and
fingerprint. Archiving it and switching the citation to the archive id is a follow-up.
