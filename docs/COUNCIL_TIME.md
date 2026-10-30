# Council time: how long the Council spent on what

The second lane of Council Watch records attention: how much meeting time, and how much written
correspondence, each part of the Council's business drew, meeting by meeting. It pairs with the
commitments lane. One shows what the Council spent its time on, the other what it undertook to do.

The data is built in two parts, kept apart as AGENTS.md requires: computed facts, and reviewed
classification.

## Computed: `data/generated/council-time/`

`python3 -m councilwatch council-time --archive PATH` regenerates it from a clean checkout of the
archive and the reviewed inputs below. `reproduce-council-time` checks it byte for byte; CI runs
that against the archive commit recorded in `meta.json`.

| File | One record per |
|---|---|
| `segments.json` | Segment of a caption transcript, as the archive's L3 transcript structure divides it: an agenda item or a procedural block, with its minutes and the minutes of public comment within it |
| `correspondence.json` | Correspondence heading in an annotated agenda (archive L2 record): the items it is filed under, and its letters from the public and from officials |
| `turns.json` | Reviewed speaker turn on a thread during general or consent public comment, with its minutes |
| `meta.json` | The pinned archive commit, counts, the estimate's calibration, and exceptions |

**Minutes.**
- A timestamped (Zoom) transcript gives caption time: a segment's end minus its start.
- A court-reporter transcript (most of 2025) has no timestamps. A segment's minutes are its share of
  the transcript's words times the meeting's length: adjournment minus call to order minus recesses,
  from the reviewed clock. These are estimates and are marked `estimated`. Tested on the timestamped
  transcripts, across 89 segments of ten minutes or more, the estimate's median ratio to caption time
  is 1.01, the middle half lie between 0.98 and 1.05, and the extremes are 0.78 and 1.13.
- Public comment is the item's public-comment span. Everything else in an item (presentations,
  questions, deliberation, motions, votes) is staff and Council time. Recesses are their own
  segments.

**Item boundaries are not authoritative.** The L3 structure was read from the transcript and not
yet checked against video (`boundary_level: inferred`). Every segment carries the words where it
begins (`evidence_start`) and its locator, so anyone can check it.

**Correspondence.** The Clerk's counts: one per listed entry, the "(n)" printed after a name, or the
N of "N similarly worded form letters". An entry the Clerk lists as submitted by a Councilmember,
the Mayor, City staff or a commission is counted under `letters_official`, by the rule in
`council_time.OFFICIAL`; everything else is the public's.

**Meetings outside the Council's listing.** Joint Powers Financing Authority, Successor Agency and
committee meetings in a joint transcript have `meeting_id: null`: the City lists them apart from
Council meetings.

## Reviewed: `data/review/council-time/`

| File | Holds |
|---|---|
| `threads.json` | The threads; the thread of every segment, including `routine`; an Auditor tag for items presented by or about the City Auditor; and the thread of a correspondence heading |
| `clock.json` | For each court-reporter transcript: call to order, adjournment and recess minutes, each with its basis (the transcript's words or the annotated agenda) |
| `turns.json` | Speaker turns on a thread outside its own agenda item, with a quotation the generator must find in the transcript at that turn |
| `links.json` | Where a speaker or a recorded action tied two threads together, with the quotation or action and its timestamp |

`threads.json` also holds `matters`, the thread of each tracked matter (the commitments page groups
by it, and validation requires one for every matter), and `decisions`, the agenda items marked on a
thread's chart. A decision names its meeting and item and a short label; the page takes the final
vote from the annotated agenda's L2 record, never from the label.

**What a thread is.** A subject grouping of heard items, so their time can be read side by side. It
is a classification, not a finding about any item. An audit is filed under its subject, and the
Auditor tag marks it across threads. Routine business (ceremony, the consent calendar as a block,
Council and City Manager comments, general public comment, adjournment) is classified `routine` and
not counted toward any thread, except for turns in `turns.json`.

**Letters take the thread of their item.** Correspondence filed under a heard item takes that item's
thread; correspondence under a subject heading takes the heading's thread in `threads.json`. A
heading not listed there is not counted toward any thread. That includes a statewide "California's
911 Rebuild" form-letter campaign (June 2026).

**Gaza.** The Council had one agenda item on it, at the April 28, 2025 special meeting. Elsewhere,
turns in `turns.json` count the time of individual speakers' turns about Gaza, Israel or Palestine
during general and consent public comment. A turn whose only such content is a sign-off is not
counted, and neither is a mention inside comment on another item: that time stays with the item.
`extent` is `partial` when the turn was mostly about something else and Gaza, Israel or Palestine
came up only in part of it; the whole turn's minutes are recorded either way, and a page must say
which it counts. A turn records its words (`quote`), not who spoke: the locator finds the speaker.

**Changing a classification.** Edit the file in a pull request and say why. A reclassification
changes what the pages show, so it is reviewed like any tracked record. `python3 -m councilwatch
validate` checks every thread id and requires every generated segment to be classified.

Member pages, and the reviewed files they use (`motions.json`, `cosponsors.json`, and the
`items` in `threads.json`), are described in [MEMBERS.md](MEMBERS.md).

**Meeting time is not all of the Council's time.** Minutes measure meeting time. An item a member
writes takes Council and staff time before any meeting (drafting, agenda review, staff and legal
review) whether or not it is ever discussed, and most member items are adopted on consent without
discussion. No record measures that time, so the pages count member-authored items by thread,
heard or not, beside the minutes.

## The consent calendar

`consent.json` lists every item adopted on the consent calendar (or moved onto it from the action
calendar), less relinquishments of office funds, donations, minutes and withdrawn items. For each it
records what the annotated agenda shows (`reasons`): an ordinance or appropriations change, member
authorship, a move from the action calendar, revision at adoption, speakers, letters filed. An item
with any of these is `policy_bearing`. Its amount is as printed: the largest figure under Financial
Implications, otherwise the first in the Recommendation (read from the archive's L1 text at the
item's lines).

**Appropriations ordinance.** The base budget is adopted on the action calendar and is listed
without an amount. An amendment counts once, at its first reading, on its net appropriation (the
Action's figure where it revised the Recommendation's); its second reading is listed without one.
Amendments are not cumulative: each states its own adjustment.

Each consent item's subject is in `threads.json` → `items`, proposed by the subject rules and
reviewed like any classification. On each thread's chart, a tick per meeting marks its consent
items: filled when any is policy-bearing, its height the largest such amount on a log scale from
$1,000 to $1 billion, a numeral when there are several. Every item is listed on the thread's page.

## Pages

- `time/index.html`: one row per thread on a shared date axis and minutes scale, City finances first
  as five rows of their own; totals by thread; every heard item ranked by minutes; City Auditor
  items; connections; and the largest correspondence headings not counted toward any thread.
- `time/<thread>.html`: the thread's chart, its decisions with their final votes, and a table of
  every meeting with what was heard, minutes and letters.
- `commitments/index.html`: every commitment, grouped by its matter's thread, open first.
- Meeting pages show how the meeting's time divided; matter pages show the time on their items.

Charts are SVG written at build time. Every figure a chart shows is also in a table on the same
page. **Gaza turns count only when `extent` is `whole`;** the Gaza page states how many partial turns
were left out and their minutes.

**The home page leads with questions.** Each is a factual question the site answers, linking to the
view that answers it (`time_site.QUESTIONS`). A question states no conclusion and implies none: it
asks how much, how many, when, or what the record shows. A question is shown only when the page and
anchor it links to exist. The questions appear one at a time by CSS alone, pausing on hover or
focus, and as a plain list when the reader chooses "Show all questions", when motion is reduced, or
when CSS is off.

## Where this came from

The classification was first made in the Council Scorecards project's council-time study and
exported with its `research/council-time-by-thread/scripts/export_watch.py`. Generated here from the
archive, the minutes for each thread agree with that study's to within half a minute, and the
letters to within about ten per thread (the two parse the Clerk's correspondence headings slightly
differently). Nine turn quotations were trimmed to the words the transcript holds.
