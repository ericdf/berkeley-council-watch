# Historical backfill: Pass 2, accountability candidates

Implements Pass 2 of AUTOMATION_SPEC.md §7. Pass 1, completing missing sources in the archive, is
not built yet. It needs the archive's policy change; until then its work list is this pass's
`annotated_agenda_not_archived` exceptions.

## What it does

`python3 -m councilwatch candidates --archive PATH --start 2021-01-19 --end YYYY-MM-DD` reads every
archived City Council annotated agenda at the archive's current commit and writes **review bundles**
to `_backfill/` (not committed): `candidates-<year>.json`, `candidates-<year>.md` and `report.json`.
Every candidate is `unconfirmed`. Nothing is written to `data/tracked/` or
`data/generated/agenda-intake/`. A confirmed candidate becomes a tracked record only through a
reviewed PR (TRACKED.md).

The pipeline is deterministic and uses no model:

1. **Text.** Use the archive's L1 text for the annotated agenda. Where the archive has none, run the
   archive's own extraction command (`pdftotext -layout`) on the archived PDF. The bundle records which
   basis each meeting used.
2. **Items.** Parse items only inside agenda calendars (Consent, Action, Information, Council Items,
   Worksession), with their title, section, fields (From, Recommendation, Action, Vote) and the pages
   they span. Ceremonial lists, comments sections and Communications are skipped.
3. **Directions.** Apply the phrase rules in `councilwatch/candidate_rules.json` (versioned) to the
   Recommendation, Action and Policy Committee Recommendation fields: report back, return to Council,
   provide an update, annually thereafter, check back, refer to or direct the City Manager, within N
   days. Each match keeps the sentence it occurs in, exactly as printed.
4. **Deadlines.** Capture "by/for/in/before <Month or Season> <Year>". A deadline in the recorded
   **Action** wins over one in the Recommendation, because the Council's action is what was decided.
   Both are kept.
5. **Follow-up reports.** Items titled as status reports, updates or annual reports are candidates in
   their own right. Referrals, contracts, ordinances and resolutions that merely mention an update are
   excluded.
6. **Links.** Propose a follow-up for a direction when all of the following hold. The evidence is
   written into the bundle.
   - It is a later follow-up item, inside the window: the effective deadline plus 180 days, or two
     years when no deadline is captured.
   - It shares at least two title words with the direction.
   - The rarity score of those shared words, the sum of log(titles / titles containing the word),
     reaches 10. Rarity is computed over the **whole** archived corpus, so a link never depends on the
     requested date range. "Restaurant" and "inspection" clear the bar; "ordinance" and "code" do not.
7. **Quote check.** Every quoted sentence and recorded action must appear, whitespace-normalized, on
   the pages the candidate cites. Page headers are stripped the same way the parser skips them. The
   command fails on any mismatch. This check would reject an invented quote from any finder, including
   a future AI one.

## Running it

- **Locally:** a clean archive checkout and `pdftotext` (poppler) are needed.
- **In GitHub:** run the **Backfill candidates** workflow (Actions tab, Run workflow) with a date range.
  It sparse-clones the archive's annotated agendas, runs the pass and uploads the bundles as an
  artifact. It has read-only permissions and no secrets.
- **Replay fixture:** CI runs `python3 -m councilwatch replay-check --archive PATH` on every PR, which
  is the acceptance criterion in AUTOMATION_SPEC.md §12. It checks that the July 30, 2024 Item 18
  direction links to the December 10, 2024 Item 22 status report as an unconfirmed candidate, with the
  deadline December 2024 taken from the Council's recorded action. The Auditor's January 2025 stays as
  a secondary deadline.

## Reviewing a bundle

Read `candidates-<year>.md`. For each candidate, decide one of:
- **reject** it;
- **confirm it as a commitment**, written in `data/tracked/` with its citation and locator;
- **confirm a proposed follow-up**, written as an event linked to that commitment, with its status
  entry.

The rule-match counts in `report.json` show which rules are noisy. A rule change bumps the rules
`version`, which every bundle records.

## First full run (archive commit 7a22d84, January 19, 2021 to October 28, 2026)

- 269 meetings scanned; 4,013 items parsed (202 from archive L1 text, 67 by run-time extraction).
- 509 candidates: 370 directions and 139 follow-up reports.
- 12 directions with proposed follow-ups (25 links). They include the Restaurant Inspections and
  Homeless Response Team audit status reports, the Financial Condition status reports, and the BPD
  hate-crimes updates. One is plainly wrong: two different "task force" items.
- 0 quote-check failures.
- 56 exceptions: 45 annotated agendas the City lists but the archive lacks (Pass 1's list), and 11
  special-meeting agendas with no numbered items.
- Run time about 5 seconds; no tokens.

Recall is the known limit. A follow-up whose title shares no uncommon words with its direction is not
proposed. Measuring how much an AI finder would add is the planned pilot: compare its candidates with
reviewed decisions on one year, all of its output checked by the same quote check.
