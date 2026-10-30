# Reviewing backfill candidates

How to turn a year's Pass 2 bundle (BACKFILL.md) into reviewed tracked records. Every judgment stays
with the reviewer. The code handles the mechanics: source records, citations, quotes, dates, due
dates and events come from the bundle and the archive, and the reviewer never types record text.

## The loop, one year at a time

1. **Generate the bundle.** Run from Council Watch with a clean archive checkout at the commit you mean
   to cite.

   ```bash
   python3 -m councilwatch candidates --archive ../berkeley-public-records --start 2024-01-01 --end 2024-12-31 --out _backfill
   ```

   This gives `_backfill/candidates-2024.md` to read and `candidates-2024.json` for the importer. Both
   record the archive commit.
2. **Decide.** Write `data/review/decisions-2024.json` (format below). Start with the directions that
   have proposed follow-ups, then the rest.
3. **Import and check.**

   ```bash
   python3 -m councilwatch import-decisions --bundle _backfill/candidates-2024.json --decisions data/review/decisions-2024.json --archive ../berkeley-public-records
   ```

   It writes `data/tracked/` and runs the validator. Nothing is written if any decision is malformed.
   Re-running with the same decisions is a no-op, and a changed decision on an imported record is
   refused rather than overwriting it.
4. **Look at the pages.** Run `python3 -m councilwatch build`, then open `_site/matters/`.
5. **Open one PR per year**, containing the decisions file and the new records. Merging is the
   publication decision.

Decisions can be added in several sittings: the importer reports how many candidates are still
undecided.

## Decisions file

```json
{
 "year": "2024",
 "rules_version": 4,
 "archive_commit": "<the bundle's archive commit>",
 "reviewed_on": "2026-10-28",
 "decisions": [
  {"candidate_id": "city-council-2024-03-12--item-7", "decision": "reject",
   "reason": "A referral to study an idea, with no deliverable or date that can be checked."},

  {"candidate_id": "city-council-2024-07-30--item-18", "decision": "confirm",
   "matter": {"id": "restaurant-inspections-audit-2024", "kind": "audit",
              "title": "Restaurant Inspections audit (City Auditor, 2024)",
              "description": "The City Auditor's audit of the restaurant inspection program and the Council's direction that the City Manager report back on it."},
   "commitment": {"label": "City Manager report back on the audit recommendations",
                  "actor": "City Manager", "kind": "report_back"},
   "links": [{"to": "city-council-2024-12-10--item-22", "decision": "confirm",
              "status": "reported_complete", "actor": "City Manager",
              "basis": "The first status report was on the December 10, 2024 agenda, the month the Council set."}]}
 ]
}
```

- **Reject** with a short, factual `reason`. Rejections are kept: they show what was examined and why
  it is not tracked.
- **Confirm** a *direction* as a commitment. Give either a new `matter` (id, title, description) or an
  existing `matter_id`, plus `commitment.label`, `actor` (as named in the record) and `kind`
  (`report_back`, `deliverable`, `deadline`, `spending_condition`, `outcome_measure`).
- `quote_field` (optional) picks which field's sentence becomes the statement. The default is the
  Action, the Council's decision.
- **For each proposed follow-up**, either confirm it with a `status` and a one-sentence `basis`, or
  reject it with a `reason`.
  - The allowed statuses are `in_progress_reported`, `reported_complete`, `reported_not_met`, `delayed` and
    `cancelled_or_superseded`.
  - An agenda item is never independent evidence, so `completion_verified` is not allowed here.
- A follow-up report is confirmed only as a link on its direction, never as a commitment by itself.

## What to confirm

Confirm when the record states a **checkable** future act: who must do what, by when or on what
cadence. A report back by a date, an ordinance to return, or annual reporting all qualify.

Reject:
- routine referrals with no deliverable or date;
- procedural motions;
- items where the match is incidental, for example "return to Council" describing something else.

When unsure, reject with the reason. A rejected candidate can be confirmed later; a published claim
is harder to take back.

Write labels and bases as plain description from the record. No characterization, motive or verdict.
"No update located" belongs to a later status review with a recorded search (TRACKED.md), not to
this import.

## Running a year in a fresh chat

Long sessions cost tokens because every turn re-reads the conversation so far. Give each year its own
chat and keep what it reads small. Starter prompt:

> Review the 2024 backfill candidates for Berkeley Council Watch. Read `docs/REVIEW.md` and
> `docs/TRACKED.md` in `ericdf/berkeley-council-watch`, then run the `candidates` command for 2024 and
> read only `_backfill/candidates-2024.md`. Draft `data/review/decisions-2024.json`, starting with the
> directions that have proposed follow-ups. Do not open source PDFs unless a candidate cannot be judged
> from its quotes; when you do, read only the cited pages. Ask me about anything you would reject or
> confirm with less than clear support. Then run `import-decisions`, `validate` and the tests, and open
> one PR.

To spend less:
- Work from the Markdown bundle, not the JSON.
- Read source pages only for the hard cases, and only the cited pages.
- Split a large year into halves (`--start`/`--end`) across two sittings, not one long one.
- A batch of mostly obvious rejections is cheap to draft with a smaller model. Have a stronger model,
  or yourself, check every confirm.
